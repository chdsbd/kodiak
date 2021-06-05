from kodiak.dependencies import (
    DependabotUpdate,
    _compare_versions,
    _extract_versions,
    dep_version_from_title,
    parse_dependabot_metadata,
)


def test_extract_versions() -> None:
    for title, version, upgrade in [
        (
            "Bump pip from 20.2.4 to 20.3 in /.github/workflows",
            ("20.2.4", "20.3"),
            "minor",
        ),
        ("Bump lodash from 4.17.15 to 4.17.19", ("4.17.15", "4.17.19"), "patch"),
        ("Update tokio requirement from 0.2 to 0.3", ("0.2", "0.3"), "minor"),
        (
            "Bump jackson-databind from 2.9.10.1 to 2.10.0.pr1 in /LiveIngest/LiveEventWithDVR",
            ("2.9.10.1", "2.10.0.pr1"),
            "minor",
        ),
        (
            "Bump commons-collections from 4.0 to 4.1 in /eosio-explorer/Quantum",
            ("4.0", "4.1"),
            "minor",
        ),
        (
            "[Snyk] Security upgrade engine.io from 3.5.0 to 4.0.0",
            ("3.5.0", "4.0.0"),
            "major",
        ),
        ("Bump lodash", None, None),
        ("Bump lodash to 4.17.19", None, None),
        ("Bump lodash from 4.17.15 to", None, None),
    ]:
        assert _extract_versions(title) == version
        assert dep_version_from_title(title) == upgrade


def test_compare_versions() -> None:
    for old_version, new_version, change in [
        ("20.2.4", "20.3", "minor"),
        ("4.17.15", "4.17.19", "patch"),
        ("0.2", "0.3", "minor"),
        ("2.9.10.1", "2.10.0.pr1", "minor"),
        ("4.0", "4.1", "minor"),
        ("1.5", "2.0", "major"),
        ("feb", "may", None),
    ]:
        assert (
            _compare_versions(old_version=old_version, new_version=new_version)
            == change
        )


def test_parse_dependabot_metadata_success() -> None:
    EXAMPLE_COMMIT_MESSAGE = """\
Bump rollup from 2.50.1 to 2.50.6
Bumps [rollup](https://github.com/rollup/rollup) from 2.50.1 to 2.50.6.
- [Release notes](https://github.com/rollup/rollup/releases)
- [Changelog](https://github.com/rollup/rollup/blob/master/CHANGELOG.md)
- [Commits](rollup/rollup@v2.50.1...v2.50.6)

---
updated-dependencies:
- dependency-name: rollup
  dependency-type: direct:development
  update-type: version-update:semver-patch
...

Signed-off-by: dependabot[bot] <support@github.com>
"""
    assert parse_dependabot_metadata(EXAMPLE_COMMIT_MESSAGE) == [
        DependabotUpdate(
            dependency_name="rollup",
            dependency_type="direct:development",
            update_type="version-update:semver-patch",
        )
    ]


def test_parse_dependabot_metadata_invalid_metadata() -> None:
    EXAMPLE_COMMIT_MESSAGE = """\
Bump rollup from 2.50.1 to 2.50.6
Bumps [rollup](https://github.com/rollup/rollup) from 2.50.1 to 2.50.6.
- [Release notes](https://github.com/rollup/rollup/releases)
- [Changelog](https://github.com/rollup/rollup/blob/master/CHANGELOG.md)
- [Commits](rollup/rollup@v2.50.1...v2.50.6)

---
updated-dependencies:

...

Signed-off-by: dependabot[bot] <support@github.com>
"""
    assert parse_dependabot_metadata(EXAMPLE_COMMIT_MESSAGE) == []


def test_parse_dependabot_metadata_missing() -> None:
    EXAMPLE_COMMIT_MESSAGE = """\
Bump rollup from 2.50.1 to 2.50.6
Bumps [rollup](https://github.com/rollup/rollup) from 2.50.1 to 2.50.6.
- [Release notes](https://github.com/rollup/rollup/releases)
- [Changelog](https://github.com/rollup/rollup/blob/master/CHANGELOG.md)
- [Commits](rollup/rollup@v2.50.1...v2.50.6)


Signed-off-by: dependabot[bot] <support@github.com>
"""
    assert parse_dependabot_metadata(EXAMPLE_COMMIT_MESSAGE) == []
