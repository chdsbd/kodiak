from typing import Sequence, Union

import markupsafe
import pydantic
import toml
from typing_extensions import Protocol

FOOTER = """
If you need help, you can open a GitHub issue, check the docs, or reach us privately at support@kodiakhq.com.

[docs](https://kodiakhq.com/docs/troubleshooting) | [dashboard](https://app.kodiakhq.com) | [support](https://kodiakhq.com/help)

"""


def format(msg: str) -> str:
    return msg + "\n" + FOOTER


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
    return format(
        f"""\
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
"""
    )


def get_markdown_for_paywall() -> str:
    return format(
        """\
You can start a 30 day trial or update your subscription on the Kodiak dashboard at https://app.kodiakhq.com.

Kodiak is free to use on public repositories, but requires a subscription to use with private repositories.

See the [Kodiak docs](https://kodiakhq.com/docs/billing) for more information about free trials and subscriptions.
"""
    )


def get_markdown_for_push_allowance_error(*, branch_name: str) -> str:
    return format(
        f"""\
Your branch protection setting for `{branch_name}` has "Restrict who can push to matching branches" enabled. You must allow Kodiak to push to this branch for Kodiak to merge pull requests.

See the Kodiak troubleshooting docs for more information: https://kodiakhq.com/docs/troubleshooting#restricting-pushes
"""
    )


class APICallRetry(Protocol):
    @property
    def api_name(self) -> str: ...

    @property
    def http_status(self) -> str: ...

    @property
    def response_body(self) -> str: ...


def get_markdown_for_api_call_errors(*, errors: Sequence[APICallRetry]) -> str:
    formatted_errors = "\n".join(
        f"- API call {error.api_name!r} failed with HTTP status {error.http_status!r} and response: {error.response_body!r}"
        for error in errors
    )
    return format(
        f"""\
Errors encountered when contacting GitHub API.

{formatted_errors}
"""
    )
