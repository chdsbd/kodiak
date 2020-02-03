import pytest


@pytest.fixture(autouse=True)
def configure_structlog() -> None:
    """
    Configures cleanly structlog for each test method.
    https://github.com/hynek/structlog/issues/76#issuecomment-240373958
    """
    import structlog

    structlog.reset_defaults()
    structlog.configure(
        processors=[
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.KeyValueRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )
