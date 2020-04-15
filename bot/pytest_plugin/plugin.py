import os

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests(args, early_config, parser):
    os.environ["SECRET_KEY"] = "some-random-key"
    os.environ["DEBUG"] = "1"
    os.environ["REDIS_URL"] = "redis://localhost:6379"
    os.environ["GITHUB_APP_ID"] = "00000"
    os.environ["GITHUB_APP_NAME"] = "kodiak-test-app"
    os.environ[
        "GITHUB_PRIVATE_KEY"
    ] = "-----BEGIN RSA PRIVATE KEY-----\nmockPrivateKeyDataSDLFKJSDLFSDLFJSDLKJF\n-----END RSA PRIVATE KEY-----\n"
