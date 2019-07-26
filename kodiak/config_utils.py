import json
from pprint import pformat
from typing import Union

import pydantic
import toml
from markupsafe import escape

from kodiak.config import V1


def get_markdown_for_config(
    error: Union[pydantic.ValidationError, toml.TomlDecodeError],
    config_str: str = "",
    git_path: str = "`master:.kodiak.toml`",
) -> str:
    config_escaped = escape(config_str)
    if isinstance(error, pydantic.ValidationError):
        error_escaped = f"# pretty \n{error}\n\n\n# json \n{error.json()}"
    else:
        error_escaped = escape(repr(error))
    return f"""\
## configuration file
> from: {git_path}
> line count: {len(config_str)}

<pre>
{config_escaped}
</pre>

## configuration error message
<pre>
{error_escaped}
</pre>

## notes
- Setup information can be found in the [Kodiak README](https://github.com/chdsbd/kodiak/blob/master/README.md)
- Example configuration files can be found in [kodiak/test/fixtures/config](https://github.com/chdsbd/kodiak/tree/master/kodiak/test/fixtures/config)
- The Python models can be found in [kodiak/config.py](https://github.com/chdsbd/kodiak/blob/master/kodiak/config.py)

"""
