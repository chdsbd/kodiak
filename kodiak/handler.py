import typing
import toml
import structlog
import asyncio

from kodiak import config
from kodiak.evaluation import evaluate_mergability, Failure, MergeErrors
from kodiak.queries import Client, RepoInfo, PullRequest, MergePRUnprocessable

log = structlog.get_logger()

CONFIG_FILE_PATH = ".kodiak.toml"


def create_git_revision_expression(branch: str, file_path: str) -> str:
    return f"{branch}:{file_path}"


# TODO: Combine into root_handler. Centralize all the stateful calls
async def find_event_data(
    owner: str, repo: str, pr_number: int, installation_id: int
) -> typing.Tuple[
    typing.Optional[typing.Union[config.V1, toml.TomlDecodeError, ValueError]],
    typing.Optional[PullRequest],
]:
    async with Client() as client:
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
        return (cfg, event_info.pull_request)


class Retry:
    pass


async def merge_pr(
    pr_id: str,
    sha: str,
    installation_id: int,
    title: typing.Optional[str] = None,
    body: typing.Optional[str] = None,
) -> typing.Optional[Retry]:
    log.info("attempting to merge pr", sha=sha, title=title, body=body)
    async with Client() as client:
        res = await client.merge_pr(
            pr_id=pr_id, sha=sha, installation_id=installation_id
        )
        if res is None:
            return None
        if isinstance(res, MergePRUnprocessable):
            return Retry()
        # ignore any other errors for now
        log.warning("An error occurred when trying to merge the PR", res=res)
        return None


async def root_handler(
    owner: str,
    repo: str,
    pr_number: int,
    installation_id: int,
    retry_attempt: bool = False,
) -> None:
    if retry_attempt:
        log.info("retrying evaluation with delay")
        await asyncio.sleep(2)
    cfg, pull_request = await find_event_data(
        owner, repo, pr_number, installation_id=installation_id
    )
    if isinstance(cfg, toml.TomlDecodeError) or isinstance(cfg, ValueError):
        log.warning("Configuration could not be parsed", cfg=cfg)
        return
    if cfg is None:
        log.warning("Configuration could not be found", cfg=cfg)
        return
    if pull_request is None:
        log.warning("Pull request could not be found", pr_number=pr_number)
        return
    res = await evaluate_mergability(config=cfg, pull_request=pull_request)
    if isinstance(res, Failure):
        should_retry = (
            # we are not in a retry attempt a the moment
            not retry_attempt
            # we only have an UNKNOWN status issue, which means that the mergeability evaluation on Github's side hasn't been completed yet
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
        log.warning("Pull request is not eligible to be merged", problems=res.problems)
        return
    res = await merge_pr(
        pr_id=pull_request.id,
        sha=pull_request.latest_sha,
        installation_id=installation_id,
    )
    if res is None:
        return None
    if not retry_attempt and isinstance(res, Retry):
        # retry request if we get an error with a merge
        asyncio.create_task(
            root_handler(owner, repo, pr_number, installation_id, retry_attempt=True)
        )
    return None
