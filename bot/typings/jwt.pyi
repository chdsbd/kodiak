from typing_extensions import Literal

def encode(
    *, payload: dict[str, object], key: str, algorithm: Literal["RS256"]
) -> bytes: ...
