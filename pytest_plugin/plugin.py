import os

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests(args, early_config, parser):
    os.environ["SECRET_KEY"] = "some-random-key"
    os.environ["DEBUG"] = "1"
    os.environ['REDIS_URL'] = ''
