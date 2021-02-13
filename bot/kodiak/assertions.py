from typing import NoReturn


def assert_never(value: NoReturn) -> NoReturn:
    """
    Enable exhaustiveness checking when comparing against enums and unions
    of literals.
    """
    raise Exception(f"expected never, got {value}")
