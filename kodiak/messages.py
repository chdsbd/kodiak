from typing import Union

import markupsafe
import pydantic
import toml


def get_markdown_for_config(
    error: Union[pydantic.ValidationError, toml.TomlDecodeError],
    config_str: str,
    git_path: str,
) -> str:
    config_escaped = markupsafe.escape(config_str)
    if isinstance(error, pydantic.ValidationError):
        error_escaped = f"# pretty \n{error}\n\n\n# json \n{error.json()}"
    else:
        error_escaped = markupsafe.escape(repr(error))
    line_count = config_str.count("\n") + 1
    return f"""\
You have an invalid Kodiak configuration file.

## configuration file
> config_file_expression: {git_path}
> line count: {line_count}

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
- The corresponding Python models can be found in [kodiak/config.py](https://github.com/chdsbd/kodiak/blob/master/kodiak/config.py)

If you need any help, please open an issue on https://github.com/chdsbd/kodiak.
"""
