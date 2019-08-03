import re
from pathlib import PurePosixPath
from typing import List, Optional, Tuple, Union


def find_patterns_and_owners(owners_str: str) -> List[Tuple[str, List[str]]]:
    results: List[Tuple[str, List[str]]] = []
    for line in owners_str.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue

        pattern, *owners = re.split(r"\s+", line)
        if not pattern or not owners:
            continue
        results.append((pattern, owners))
    return results


def find_owner(
    pattern_owners: List[Tuple[str, List[str]]], path: Union[PurePosixPath, str]
) -> Optional[List[str]]:
    if isinstance(path, str):
        path = PurePosixPath(path)
    for pattern, owners in reversed(pattern_owners):
        if path.match(pattern):
            return owners
    return None
