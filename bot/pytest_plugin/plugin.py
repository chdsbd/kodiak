import os

import pytest


@pytest.hookimpl(tryfirst=True)  # type: ignore[misc]
def pytest_load_initial_conftests(
    args: object, early_config: object, parser: object
) -> None:
    os.environ["SECRET_KEY"] = "some-random-key"
    os.environ["DEBUG"] = "1"
    os.environ["REDIS_URL"] = "redis://localhost:6379"
    os.environ["GITHUB_APP_ID"] = "534524"
    os.environ["GITHUB_APP_NAME"] = "kodiak-test-app"
    os.environ[
        "GITHUB_PRIVATE_KEY"
    ] = "-----BEGIN RSA PRIVATE KEY-----\nmockPrivateKeyDataSDLFKJSDLFSDLFJSDLKJF\n-----END RSA PRIVATE KEY-----\n"
    os.environ["SUBSCRIPTIONS_ENABLED"] = "1"
