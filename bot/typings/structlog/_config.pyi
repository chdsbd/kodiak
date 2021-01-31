from typing import Any, Optional

from structlog.stdlib import BoundLogger

def reset_defaults() -> None: ...
def configure(
    processors: Optional[Any] = ...,
    wrapper_class: Optional[Any] = ...,
    context_class: Optional[Any] = ...,
    logger_factory: Optional[Any] = ...,
    cache_logger_on_first_use: Optional[Any] = ...,
) -> None: ...
def get_logger(*args: Any, **initial_values: Any) -> BoundLogger: ...
