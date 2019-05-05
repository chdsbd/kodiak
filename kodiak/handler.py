import typing
import toml
import structlog
import asyncio

from kodiak import config
from kodiak.evaluation import evaluate_mergability, MergeErrors
from kodiak.queries import Client, RepoInfo, PullRequest, MergePRUnprocessable

logger = structlog.get_logger()

CONFIG_FILE_PATH = ".kodiak.toml"


def create_git_revision_expression(branch: str, file_path: str) -> str:
    return f"{branch}:{file_path}"


async def root_handler(
    owner: str,
    repo: str,
    pr_number: int,
    installation_id: str,
    retry_attempt: bool = False,
) -> None:
    log = logger.bind(
        owner=owner, repo=repo, installation_id=installation_id, pr_number=pr_number
    )
    async with Client() as client:
        # we want to allow retrying requests because Github occasionally takes
        # time to reach consistency. We want to add a delay to improve our
        # changes of success.
        if retry_attempt:
            log.info("retrying evaluation with delay")
            await asyncio.sleep(2)

        log.debug("finding event data for pull request")
        # we need to make one request for the default branch name, which allows
        # us to find our configuration file on the main branch in the next
        # query. This would be solved with a join, but that's not possible in
        # GraphQL.
        default_branch_name = await client.get_default_branch_name(
            owner=owner, repo=repo, installation_id=installation_id
        )
        event_info = await client.get_event_info(
            owner=owner,
            repo=repo,
            config_file_expression=create_git_revision_expression(
                branch=default_branch_name, file_path=CONFIG_FILE_PATH
            ),
            pr_number=pr_number,
            installation_id=installation_id,
        )
        cfg = None
        if event_info.config_file is not None:
            cfg = config.V1.parse_toml(event_info.config_file)
        pull_request = event_info.pull_request

        # process query responses
        if isinstance(cfg, toml.TomlDecodeError) or isinstance(cfg, ValueError):
            log.warning("Configuration could not be parsed", cfg=cfg)
            return
        if cfg is None:
            log.warning("Configuration could not be found", cfg=cfg)
            return
        if pull_request is None:
            log.warning("Pull request could not be found")
            return
        log = log.bind(pull_request=pull_request)

        log.info("attempting to evaluate mergeability")
        res = await evaluate_mergability(config=cfg, pull_request=pull_request)
        if isinstance(res, Failure):
            should_retry = (
                # we are not in a retry attempt a the moment
                not retry_attempt
                # we only have an UNKNOWN status issue, which means that the
                # mergeability evaluation on Github's side hasn't been completed
                # yet
                and len(res.problems) == 1
                and res.problems[0] == MergeErrors.UNKNOWN
            )
            if should_retry:
                log.info("scheduling task to retry status request")
                asyncio.create_task(
                    root_handler(
                        owner, repo, pr_number, installation_id, retry_attempt=True
                    )
                )
                return
            log.info("Pull request is not eligible to be merged", problems=res.problems)
            return

        log.info("attempting to merge pr")
        merge_res = await client.merge_pr(
            pr_id=pull_request.id,
            sha=pull_request.latest_sha,
            installation_id=installation_id,
        )
        # we were successful
        if merge_res is None:
            return None
        log.warning("problems attempting to merge pr", merge_res=merge_res)
        if isinstance(merge_res, MergePRUnprocessable) and not retry_attempt:
            log.info("retrying request to recover from unprocessable error")
            # retry request
            asyncio.create_task(
                root_handler(
                    owner, repo, pr_number, installation_id, retry_attempt=True
                )
            )
        return None
