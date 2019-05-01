import pytest
from pathlib import Path
import json
import asyncio

from kodiak.test import vcr
from kodiak.queries import Client, BranchNameError, MergeStateStatus, PullRequestState


@vcr.use_cassette()
@pytest.mark.asyncio
async def test_get_default_branch_name():
    async with Client() as api:
        name = await api.get_default_branch_name("django", "django")
        assert name == "master"

        with pytest.raises(BranchNameError):
            await api.get_default_branch_name("about", "about")


@vcr.use_cassette()
@pytest.mark.asyncio
async def test_get_event_info():
    """
    - config path to no file
    - PR that has already been merged
    """
    async with Client() as api:
        merged_pr_no_config = await api.get_event_info(
            "chdsbd",
            "test_repo",
            config_file_expression="master:__invalid__config__path__.kodiak.yml",
            pr_number=1,
        )
        assert merged_pr_no_config.config_file is None
        assert merged_pr_no_config.repo is not None
        assert merged_pr_no_config.pull_request is not None
        assert merged_pr_no_config.pull_request.labels == []
        assert merged_pr_no_config.pull_request.mergeStateStatus is not None
        assert merged_pr_no_config.pull_request.state == PullRequestState.MERGED
        assert (
            merged_pr_no_config.repo.merge_commit_allowed
            and merged_pr_no_config.repo.rebase_merge_allowed
            and merged_pr_no_config.repo.squash_merge_allowed
        )


@vcr.use_cassette()
@pytest.mark.asyncio
async def test_get_event_info_normal():
    """
    - config path to file
    - PR that has not been merge
    """
    async with Client() as api:
        merged_pr_no_config = await api.get_event_info(
            "chdsbd",
            "test_repo",
            config_file_expression="master:.config.toml",
            pr_number=2,
        )
        assert merged_pr_no_config.config_file is not None
        assert merged_pr_no_config.repo is not None
        assert merged_pr_no_config.pull_request is not None
        assert merged_pr_no_config.pull_request.labels == ["duplicate"]
        assert (
            merged_pr_no_config.pull_request.mergeStateStatus == MergeStateStatus.CLEAN
        )
        assert merged_pr_no_config.pull_request.state == PullRequestState.OPEN


@pytest.fixture
def private_key():
    return (
        Path(__file__).parent / "test" / "fixtures" / "github.voided.private-key.pem"
    ).read_text()


@pytest.mark.asyncio
async def test_generate_jwt(private_key: str):
    async with Client(private_key=private_key, app_identifier="29196") as api:
        assert api.generate_jwt() is not None


@pytest.mark.asyncio
async def test_get_token_for_install():
    assert False


def test_token_response():
    assert False


@pytest.mark.asyncio
async def test_merge_pr():
    assert False


def load_api_fixture(file_name: str) -> str:
    return json.loads(
        (Path(__file__).parent / "test" / "fixtures" / "api" / file_name).read_text()
    )


@pytest.mark.asyncio
async def test_merge_pr_unprocessable(mocker):
    res = load_api_fixture("merge_unprocessable.json")
    patched = mocker.patch("kodiak.queries.Client.send_query")
    future: asyncio.Future[dict] = asyncio.Future()
    future.set_result(res)
    patched.return_value = future
    async with Client(token="blah") as api:
        # we should not explode when we receive an "UNPROCESSABLE" response from the Github api
        await api.merge_pr(pr_id="DSLFKJS", sha="223490", installation_id=123)
