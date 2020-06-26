#!/usr/bin/env python3

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Mapping, Optional

APP_LABEL = "core"

MIGRATIONS_DIRECTORY = "./core/migrations"


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__file__)


def is_installed(name: str) -> bool:
    return which(name) is not None


def get_migration_id(filename: str) -> str:
    return Path(filename).stem.split("_")[0]


@dataclass(frozen=True)
class PRInfo:
    owner: str
    repo: str
    pr_number: str


def get_pr_info(env: Mapping[str, str]) -> Optional[PRInfo]:
    circle_pr = env.get("CIRCLE_PULL_REQUEST")
    if circle_pr is None:
        return None
    _, _, _, owner, repo, _, pr_number = circle_pr.split("/")

    return PRInfo(owner=owner, repo=repo, pr_number=pr_number)


def main() -> None:
    # circle's built in git checkout code clobbers the `master` ref so we do the
    # following to make it not point to the current ref.
    # https://discuss.circleci.com/t/git-checkout-of-a-branch-destroys-local-reference-to-master/23781/7
    if os.getenv("CIRCLECI"):
        subprocess.run(["git", "branch", "-f", "master", "origin/master"], check=True)

    diff_cmd = [
        "git",
        "--no-pager",
        "diff",
        "--name-only",
        "master..",
        MIGRATIONS_DIRECTORY,
    ]

    changed_migrations_ids = [
        (get_migration_id(p), p)
        for p in subprocess.run(diff_cmd, capture_output=True, check=True)
        .stdout.decode()
        .split()
    ]
    log.info("found migrations: %s", changed_migrations_ids)

    # get sqlmigrate to behave
    os.environ.setdefault("STRIPE_ANNUAL_PLAN_ID", "1")

    output_files = []

    for migration_id, filename in changed_migrations_ids:
        log.info("getting sql for %s", filename)
        output_sql_file = (Path(".") / filename).with_suffix(".sql").open(mode="w")
        subprocess.run(
            ["poetry", "run", "manage.py", "sqlmigrate", APP_LABEL, migration_id],
            stdout=output_sql_file,
            check=True,
        )
        log.info("running squawk for %s", filename)
        output_files.append(output_sql_file.name)

    log.info("sql files found: %s", output_files)

    if not output_files:
        return

    if not is_installed("squawk"):
        subprocess.run(["npm", "config", "set", "unsafe-perm", "true"], check=True)
        log.info("squawk not found, installing")
        subprocess.run(["npm", "install", "-g", "squawk-cli@0.2.2"], check=True)

    pr_info = get_pr_info(os.environ)
    assert pr_info is not None
    log.info(pr_info)

    os.environ.setdefault("SQUAWK_GITHUB_PR_NUMBER", pr_info.pr_number)
    os.environ.setdefault("SQUAWK_GITHUB_REPO_NAME", pr_info.repo)
    os.environ.setdefault("SQUAWK_GITHUB_REPO_OWNER", pr_info.owner)

    log.info(
        subprocess.run(
            ["squawk", "upload-to-github", *output_files],
            capture_output=True,
            check=True,
        )
    )


if __name__ == "__main__":
    main()
