import typing
import inspect
from pathlib import Path


def build_cassette_path(function: typing.Callable) -> str:
    """
    Ensure that we store cassettes in __cassettes__ subdirectory of folder with .yml as the extension.

    Ex:
    build_cassette_path(test_call_api) == "dir/__cassettes__/test_call_api.yml"
    """
    path = (
        Path(inspect.getfile(function)).parent
        / "__cassettes__"
        / Path(function.__name__).with_suffix(".yml")
    )
    return str(path)


HEADER_IGNORE_PARTIALS = ("ratelimit", "etag", "last-modified", "request-id")


def ignoreable_header(name: str) -> bool:
    for header_name in HEADER_IGNORE_PARTIALS:
        if header_name in name.lower():
            return True
    return False


def scrub_response(response: typing.Dict):
    """
    Remove fields that change like `Date` to reduce churn
    """
    new_headers = []
    for name, value in response["headers"]:
        if name == "date":
            new_headers.append([name, "Thu, 20 May 2010 12:30:20 GMT"])
            continue
        if ignoreable_header(name):
            continue
        new_headers.append(([name, value]))
    response["headers"] = new_headers

    return response


from vcr import VCR


vcr = VCR(
    func_path_generator=build_cassette_path,
    before_record_response=scrub_response,
    filter_headers=[("User-Agent", None), ("Authorization", None)],
    record_mode="new_episodes",
)
