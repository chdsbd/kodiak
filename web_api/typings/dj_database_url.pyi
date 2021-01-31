from typing import Optional

from typing_extensions import TypedDict

class DBConfig(TypedDict):
    NAME: str
    USER: str
    PASSWORD: str
    HOST: str
    PORT: str
    CONN_MAX_AGE: int
    ENGINE: str

def parse(
    url: str,
    engine: Optional[str] = None,
    conn_max_age: int = 0,
    ssl_require: bool = False,
) -> DBConfig: ...
