"""
Tests for renovate-specific dependency behavior.

See test_dependencies and the renovate_pull_requests/ folder for more tests
using full PR examples.
"""
from __future__ import annotations

from kodiak.dependencies import dep_versions_from_renovate_pr_body


def test_renovate_minor_major() -> None:
    """
    Test with minor and major upgrades in PR.

    Example modified from https://github.com/netlify/cli/pull/2998
    """
    renovate_body = r"""

| Package | Change | Age | Adoption | Passing | Confidence |
|---|---|---|---|---|---|
| [@netlify/build](https://togithub.com/netlify/build) | [`^16.2.1` -> `^16.3.5`](https://renovatebot.com/diffs/npm/@netlify%2fbuild/16.2.1/16.3.5) | [![age](https://badges.renovateapi.com/packages/npm/@netlify%2fbuild/16.3.5/age-slim)](https://docs.renovatebot.com/merge-confidence/) | [![adoption](https://badges.renovateapi.com/packages/npm/@netlify%2fbuild/16.3.5/adoption-slim)](https://docs.renovatebot.com/merge-confidence/) | [![passing](https://badges.renovateapi.com/packages/npm/@netlify%2fbuild/16.3.5/compatibility-slim/16.2.1)](https://docs.renovatebot.com/merge-confidence/) | [![confidence](https://badges.renovateapi.com/packages/npm/@netlify%2fbuild/16.3.5/confidence-slim/16.2.1)](https://docs.renovatebot.com/merge-confidence/) |
| [@netlify/config](https://togithub.com/netlify/build) | [`^13.0.0` -> `^14.0.0`](https://renovatebot.com/diffs/npm/@netlify%2fconfig/13.0.0/14.0.0) | [![age](https://badges.renovateapi.com/packages/npm/@netlify%2fconfig/14.0.0/age-slim)](https://docs.renovatebot.com/merge-confidence/) | [![adoption](https://badges.renovateapi.com/packages/npm/@netlify%2fconfig/14.0.0/adoption-slim)](https://docs.renovatebot.com/merge-confidence/) | [![passing](https://badges.renovateapi.com/packages/npm/@netlify%2fconfig/14.0.0/compatibility-slim/13.0.0)](https://docs.renovatebot.com/merge-confidence/) | [![confidence](https://badges.renovateapi.com/packages/npm/@netlify%2fconfig/14.0.0/confidence-slim/13.0.0)](https://docs.renovatebot.com/merge-confidence/) |

---
"""

    assert dep_versions_from_renovate_pr_body(renovate_body) == "major"
