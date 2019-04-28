import pytest

from kodiak.test import vcr
from kodiak.queries import Client, BranchNameError


@vcr.use_cassette()
@pytest.mark.asyncio
async def test_get_default_branch_name():
    async with Client() as api:
        name = await api.get_default_branch_name("django", "django")
        assert name == "master"

        with pytest.raises(BranchNameError):
            await api.get_default_branch_name("about", "about")
