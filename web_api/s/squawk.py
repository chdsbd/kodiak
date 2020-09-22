#!/usr/bin/env python3

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Mapping, Optional

SQUAWK_VERSION = "0.5.0"
APP_LABEL = "web_api"

MIGRATIONS_DIRECTORY = "./web_api/migrations"


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__file__)


def is_installed(name: str) -> bool:
    return which(name) is not None


MIGRATION_REGEX = re.compile(r"^(\d{4,}_\w+)\.py$")


def get_migration_id(filepath: str) -> Optional[str]:
    """
    valid migrations:
        0001_initial.py
        0014_auto_20200323_0159.py
        0023_account_limit_billing_access_to_owners.py
    invalid migrations:
        __init__.py

    For a valid migration 0001_initial.py, return 0001_initial.
    """
    filename = Path(filepath).name
    match = MIGRATION_REGEX.match(filename)
    if match is None:
        return None
    return match.groups()[0]


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
    if os.getenv("CIRCLECI") and os.getenv("CIRCLE_BRANCH") != "master":
        subprocess.run(["git", "branch", "-f", "master", "origin/master"], check=True)

    diff_cmd = [
        "git",
        "--no-pager",
        "diff",
        "--name-only",
        "master...",
        MIGRATIONS_DIRECTORY,
    ]

    changed_migrations_ids = []
    for p in (
        subprocess.run(diff_cmd, capture_output=True, check=True)
        .stdout.decode()
        .split()
    ):
        migration_id = get_migration_id(p)
        if migration_id is None:
            continue
        changed_migrations_ids.append((migration_id, p))

    log.info("found migrations: %s", changed_migrations_ids)

    # get sqlmigrate to behave
    os.environ.setdefault("STRIPE_ANNUAL_PLAN_ID", "1")
    os.environ.setdefault("DEBUG", "1")
    os.environ.setdefault("KODIAK_API_GITHUB_CLIENT_ID", "Iv1.111FAKECLIENTID111")
    os.environ.setdefault("KODIAK_API_GITHUB_CLIENT_SECRET", "888INVALIDSECRET8888")
    os.environ.setdefault("KODIAK_WEB_APP_URL", "https://app.kodiakhq.com/")
    os.environ.setdefault("STRIPE_PLAN_ID", "plan_somePlanId")
    os.environ.setdefault("STRIPE_ANNUAL_PLAN_ID", "price_annualPlanId")
    os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_someWebhookSecret")
    os.environ.setdefault("STRIPE_SECRET_KEY", "sk_someStripeSecretKey")
    os.environ.setdefault(
        "STRIPE_PUBLISHABLE_API_KEY", "pk_test_someExampleStripeApiKey"
    )
    os.environ.setdefault("DATABASE_URL", "redis://localhost:6379")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
    os.environ.setdefault("DEBUG", "1")

    output_files = []

    for migration_id, path in changed_migrations_ids:
        log.info("getting sql for %s", path)
        output_sql_file = (
            (Path(MIGRATIONS_DIRECTORY) / Path(path).name)
            .with_suffix(".sql")
            .open(mode="w")
        )
        subprocess.run(
            ["poetry", "run", "./manage.py", "sqlmigrate", APP_LABEL, migration_id],
            stdout=output_sql_file,
            check=True,
        )
        log.info("running squawk for %s", path)
        output_files.append(output_sql_file.name)

    log.info("sql files found: %s", output_files)

    if not output_files:
        return

    if not is_installed("squawk"):
        subprocess.run(["npm", "config", "set", "unsafe-perm", "true"], check=True)
        log.info("squawk not found, installing")
        subprocess.run(
            ["npm", "install", "-g", f"squawk-cli@{SQUAWK_VERSION}"], check=True
        )

    pr_info = get_pr_info(os.environ)
    assert pr_info is not None
    log.info(pr_info)

    os.environ.setdefault("SQUAWK_GITHUB_PR_NUMBER", pr_info.pr_number)
    os.environ.setdefault("SQUAWK_GITHUB_REPO_NAME", pr_info.repo)
    os.environ.setdefault("SQUAWK_GITHUB_REPO_OWNER", pr_info.owner)

    res = subprocess.run(
        ["squawk", "upload-to-github", *output_files], capture_output=True,
    )
    log.info(res)
    res.check_returncode()


if __name__ == "__main__":
    main()
