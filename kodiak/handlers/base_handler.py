import typing
import toml
import logging

from kodiak import config
from kodiak.evaluation import evaluate_mergability, Failure
from kodiak.queries import Client, RepoInfo, PullRequest

logger = logging.getLogger(__name__)


def create_git_revision_expression(branch: str, file_path: str) -> str:
    """
    example: `master:.circleci/config.yml`
    """
    return f"{branch}:{file_path}"


CONFIG_FILE_PATH = ".kodiak.toml"


async def find_event_data(
    owner: str, repo: str, pr_number: int
) -> typing.Tuple[
    typing.Optional[typing.Union[config.V1, toml.TomlDecodeError]],
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


async def merge_pr(owner: str, repo: str, pr_number: int):
    raise NotImplementedError()


async def base_handler(owner: str, repo: str, pr_number: int) -> None:
    cfg, pull_request = await find_event_data(owner, repo, pr_number)
    if isinstance(cfg, toml.TomlDecodeError):
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
    await merge_pr(owner=owner, repo=repo, pr_number=pr_number)
