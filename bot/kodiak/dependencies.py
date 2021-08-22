import re
from typing import List, Optional, Sequence, Tuple, TypeVar

from typing_extensions import Literal

title_regex = re.compile(r"from (?P<old_version>\S+) to (?P<new_version>\S+)")


def _extract_versions(x: str) -> Optional[Tuple[str, str]]:
    """
    Find old and new version from PR title
    Example:
        title: "Bump jackson-databind from 2.9.10.1 to 2.10.0.pr1 in /LiveIngest/LiveEventWithDVR"
        
        result: "2.9.10.1", "2.10.0.pr1"
    """
    match = title_regex.search(x)
    if match is None:
        return None
    group = match.groupdict()
    if "old_version" not in group or "new_version" not in group:
        return None
    return group["old_version"], group["new_version"]


# regex to split version string. Versions aren't necessarily semver.
#
# from dependabot: https://github.com/dependabot/dependabot-core/blob/998de3be7811956354aea077ecb180831e24012c/common/lib/dependabot/pull_request_creator/labeler.rb#L95-L115
version_regex = re.compile(r"[.+]")


def _parse_version_simple(x: str) -> List[str]:
    """
    Split version string into pieces.
    """
    return version_regex.split(x)


T = TypeVar("T")


def _get_or_none(arr: Sequence[T], index: int) -> Optional[T]:
    try:
        return arr[index]
    except IndexError:
        return None


def _compare_versions(
    old_version: str, new_version: str
) -> Optional[Literal["major", "minor", "patch"]]:
    """
    Determine patch, like Dependabot.

    https://github.com/dependabot/dependabot-core/blob/998de3be7811956354aea077ecb180831e24012c/common/lib/dependabot/pull_request_creator/labeler.rb#L92-L114
    """
    old_version_parts = _parse_version_simple(old_version)
    new_version_parts = _parse_version_simple(new_version)

    for part in new_version_parts[:3] + old_version_parts[:3]:
        try:
            int(part)
        except ValueError:
            return None

    if _get_or_none(new_version_parts, 0) != _get_or_none(old_version_parts, 0):
        return "major"
    if _get_or_none(new_version_parts, 1) != _get_or_none(old_version_parts, 1):
        return "minor"
    return "patch"


def dep_version_from_title(x: str) -> Optional[Literal["major", "minor", "patch"]]:
    """
    Try to determine the semver upgrade type from string.

    For example, 'Bump lodash from 4.17.15 to 4.17.19', would be "patch", since the "patch" field is upgraded from 15 to 19.
    """
    res = _extract_versions(x)
    if res is None:
        return None
    old_version, new_version = res
    return _compare_versions(old_version, new_version)


renovate_body_regex = re.compile(
    r"`\^?v?(?P<old_version>.*)` -> `\^?v?(?P<new_version>.*)`", re.MULTILINE
)

MatchType = Literal["major", "minor", "patch"]

match_rank = {"major": 3, "minor": 2, "patch": 1, None: 0}


def compare_match_type(a: MatchType, b: MatchType) -> bool:
    return match_rank[a] > match_rank[b]


def dep_versions_from_renovate_pr_body(
    body: str
) -> Optional[Literal["major", "minor", "patch"]]:
    """
    Parse update type from a Renovate PR Body.

    Renovate can batch updates, so we need to report to largest update type of the batch. For example, if the batch contained a "major"
    """
    largest_match_type = None
    for match in renovate_body_regex.finditer(body):
        group = match.groupdict()
        if "old_version" not in group or "new_version" not in group:
            continue
        match_type = _compare_versions(group["old_version"], group["new_version"])
        if not match_type:
            continue
        if compare_match_type(match_type, largest_match_type):
            largest_match_type = match_type
    return largest_match_type
