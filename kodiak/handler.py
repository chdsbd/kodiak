import typing
import toml
import logging

from kodiak import config
from kodiak.evaluation import evaluate_mergability, Failure
from kodiak.queries import Client, RepoInfo, PullRequest

logger = logging.getLogger(__name__)

CONFIG_FILE_PATH = ".kodiak.toml"


def create_git_revision_expression(branch: str, file_path: str) -> str:
    return f"{branch}:{file_path}"


# TODO: Combine into root_handler. Centralize all the stateful calls
async def find_event_data(
    owner: str, repo: str, pr_number: int
) -> typing.Tuple[
    typing.Optional[typing.Union[config.V1, toml.TomlDecodeError, ValueError]],
    typing.Optional[PullRequest],
]:
    async with Client() as client:
        default_branch_name = await client.get_default_branch_name(
            owner=owner, repo=repo
        )
        event_info = await client.get_event_info(
            owner=owner,
            repo=repo,
            config_file_expression=create_git_revision_expression(
                branch=default_branch_name, file_path=CONFIG_FILE_PATH
            ),
            pr_number=pr_number,
        )
        cfg = None
        if event_info.config_file is not None:
            cfg = config.V1.parse_toml(event_info.config_file)
        return (cfg, event_info.pull_request)


async def merge_pr(
    pr_id: str,
    sha: str,
    title: typing.Optional[str] = None,
    body: typing.Optional[str] = None,
) -> None:
    logging.info(
        "attempting to merge pr (%s) with sha (%s), title (%s) and body (%s)",
        pr_id,
        sha,
        title,
        body,
    )
    async with Client() as client:
        # TODO: Add error handling
        await client.merge_pr(pr_id=pr_id, sha=sha)


async def root_handler(owner: str, repo: str, pr_number: int) -> None:
    cfg, pull_request = await find_event_data(owner, repo, pr_number)
    if isinstance(cfg, toml.TomlDecodeError) or isinstance(cfg, ValueError):
        logger.warning("Problem parsing configuration file: %s", cfg)
        return
    if cfg is None:
        logger.warning("Could not find config file")
        return
    if pull_request is None:
        logger.warning("Could not find pull request number: %s", pr_number)
        return
    res = await evaluate_mergability(config=cfg, pull_request=pull_request)
    if isinstance(res, Failure):
        logger.warning("Pull request is not eligible to be merged: %s", res.problems)
        return
    await merge_pr(pr_id=pull_request.id, sha=pull_request.latest_sha)
