import typing
from kodiak import ghapi as gh
from kodiak.config import V1
import toml

# TODO: Make config_path configurable
async def get_config(
    org: str, repo: str, config_path: str = ".kodiak.toml"
) -> typing.Optional[V1]:
    content = await gh.get_contents(org, repo, config_path)
    if content is None:
        return None
    # cast to Dict[Any, Any] to satisfy mypy
    # Argument 1 to "parse_obj" of "BaseModel" has incompatible type "MutableMapping[str, Any]"; expected "Dict[Any, Any]"
    return V1.parse_obj(typing.cast(dict, toml.loads(content.decode())))
