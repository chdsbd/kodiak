from typing import Union

import markupsafe
import pydantic
import toml

FOOTER = """
If you need help, you can open a GitHub issue, check the docs, or reach us privately at support@kodiakhq.com.

[docs](https://kodiakhq.com/docs/troubleshooting) | [dashboard](https://app.kodiakhq.com) | [support](https://kodiakhq.com/help)
"""


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
- Check the Kodiak docs for setup information at https://kodiakhq.com/docs/quickstart.
- A configuration reference is available at https://kodiakhq.com/docs/config-reference.
- Full examples are available at https://kodiakhq.com/docs/recipes

{FOOTER}
"""


def get_markdown_for_paywall() -> str:
    return f"""\
You can update your subscription on the Kodiak dashboard at https://app.kodiakhq.com.

See the [Kodiak docs](https://kodiakhq.com/docs/billing) for more information on modifying your subscription.

{FOOTER}
"""
