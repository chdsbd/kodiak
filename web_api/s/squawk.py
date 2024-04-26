from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from pathlib import Path

SQUAWK_VERSION = "0.5.0"
APP_LABEL = "web_api"

MIGRATIONS_DIRECTORY = "./web_api/migrations"


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__file__)


_MIGRATION_REGEX = re.compile(r"^(\d{4,}_\w+)\.py$")


def _get_migration_id(filepath: str) -> str | None:
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
    match = _MIGRATION_REGEX.match(filename)
    if match is None:
        return None
    return match.groups()[0]


def _get_migration_ids() -> list[tuple[str, str]]:
    current_branch = subprocess.run(
        ["git", "branch", "--show-current"], capture_output=True, check=True
    )
    diff_cmd = [
        "git",
        "--no-pager",
        "diff",
        "--name-only",
        f"master...{current_branch}",
        MIGRATIONS_DIRECTORY,
    ]

    changed_migrations_ids = []
    for p in (
        subprocess.run(diff_cmd, capture_output=True, check=True)
        .stdout.decode()
        .split()
    ):
        migration_id = _get_migration_id(p)
        if migration_id is None:
            continue
        changed_migrations_ids.append((migration_id, p))
    return changed_migrations_ids


def main() -> None:
    try:
        changed_migrations_ids = _get_migration_ids()
    except subprocess.CalledProcessError as e:
        print(f"stderr: {e.stderr.decode()}")
        print(f"stdout: {e.stdout.decode()}")
        print(f"status code: {e.returncode}")
        sys.exit(1)

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


if __name__ == "__main__":
    main()
