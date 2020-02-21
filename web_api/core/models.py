import datetime
import logging
import uuid
from typing import Callable, List, Optional
from dataclasses import dataclass

import requests
from django.contrib.postgres import fields as pg_fields
from django.db import connection, models
from django.utils import timezone

logger = logging.getLogger(__name__)


def sane_repr(*attrs: str) -> Callable:
    """
    Copyright (c) 2019 Sentry (https://sentry.io) and individual contributors.
    All rights reserved.
    Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
        1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
        2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
        3. Neither the name Sentry nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
    https://github.com/getsentry/sentry/blob/95767d455b8004ec4b4c5026d84b64b6348e6d37/src/sentry/db/models/base.py
    """
    if "id" not in attrs and "pk" not in attrs:
        attrs = ("id",) + attrs

    def _repr(self: object) -> str:
        cls = type(self).__name__

        pairs = ", ".join((f"{a}={repr(getattr(self, a, None))}" for a in attrs))

        return f"<{cls} at 0x{id(self):x}: {pairs}>"  # flake8: noqa PIE782

    return _repr


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    __repr__ = sane_repr("id")


class SyncAccountsError(Exception):
    pass


class User(BaseModel):
    """
    A GitHub user that can login to Kodiak.

    A User can be a member of multiple Accounts if they have access.
    """

    github_id = models.IntegerField(
        unique=True, help_text="GitHub ID of the GitHub user account."
    )
    github_login = models.CharField(
        unique=True, max_length=255, help_text="GitHub username of the GitHub account."
    )
    github_access_token = models.CharField(
        max_length=255, help_text="OAuth token for the GitHub user."
    )

    class Meta:
        db_table = "user"

    __repr__ = sane_repr("github_id", "github_login")

    @property
    def is_authenticated(self) -> bool:
        return True

    def profile_image(self) -> str:
        return f"https://avatars.githubusercontent.com/u/{self.github_id}"

    def sync_accounts(self) -> None:
        """

        - create any missing installations
        - add memberships of user for installations
        - remove memberships of installations that aren't included
        """
        user_installations_res = requests.get(
            "https://api.github.com/user/installations",
            headers=dict(
                authorization=f"Bearer {self.github_access_token}",
                Accept="application/vnd.github.machine-man-preview+json",
            ),
            timeout=5,
        )
        try:
            user_installations_res.raise_for_status()
        except (requests.HTTPError, requests.exceptions.Timeout):
            logging.warning("sync_installation failed", exc_info=True)
            raise SyncAccountsError

        # TODO(chdsbd): Handle multiple pages of installations
        try:
            if user_installations_res.links["next"]:
                logging.warning("user has multiple pages")
        except KeyError:
            pass

        installations_data = user_installations_res.json()
        installations = installations_data["installations"]

        accounts: List[Account] = []

        for installation in installations:
            installation_id = installation["id"]
            installation_account_id = installation["account"]["id"]
            installation_account_login = installation["account"]["login"]
            installation_account_type = installation["account"]["type"]

            existing_account: Optional[Account] = Account.objects.filter(
                github_account_id=installation_account_id
            ).first()
            if existing_account is None:
                account = Account.objects.create(
                    github_installation_id=installation_id,
                    github_account_id=installation_account_id,
                    github_account_login=installation_account_login,
                    github_account_type=installation_account_type,
                )
            else:
                account = existing_account
                account.github_installation_id = installation_id
                account.github_account_id = installation_account_id
                account.github_account_login = installation_account_login
                account.github_account_type = installation_account_type
                account.save()

            try:
                AccountMembership.objects.get(account=account, user=self)
            except AccountMembership.DoesNotExist:
                AccountMembership.objects.create(account=account, user=self)

            accounts.append(account)

        # remove installations to which the user no longer has access.
        AccountMembership.objects.exclude(account__in=accounts).filter(
            user=self
        ).delete()


class AnonymousUser:
    @property
    def is_authenticated(self) -> bool:
        return False


class GitHubEvent(BaseModel):
    event_name = models.CharField(max_length=255, db_index=True)
    payload = pg_fields.JSONField(default=dict)

    class Meta:
        db_table = "github_event"

    __repr__ = sane_repr("event_name")


class Account(BaseModel):
    """
    An GitHub Kodiak App installation for a GitHub organization or user.

    Users are associated with Accounts via AccountMembership.
    """

    class AccountType(models.TextChoices):
        user = "User"
        organization = "Organization"

    github_installation_id = models.IntegerField(
        unique=True, help_text="GitHub App Installation ID."
    )
    github_account_id = models.IntegerField(
        unique=True, help_text="GitHub ID for account with installation."
    )
    github_account_login = models.CharField(
        unique=True,
        max_length=255,
        help_text="GitHub username for account with installation.",
    )
    github_account_type = models.CharField(max_length=255, choices=AccountType.choices)

    class Meta:
        db_table = "account"

    __repr__ = sane_repr(
        "github_installation_id", "github_account_id", "github_account_login"
    )

    def profile_image(self) -> str:
        return f"https://avatars.githubusercontent.com/u/{self.github_account_id}"


class AccountMembership(BaseModel):
    """
    Associates a User with an Account.

    A GitHub user can be associated with multiple installations of Kodiak. This
    model defines that membership.
    """

    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")

    class Meta:
        db_table = "account_membership"

    __repr__ = sane_repr("account_id", "user_id")


class PullRequestActivity(BaseModel):
    """
    Store a per-day aggregate of pull request activity.

    This information is calculated in the background from GitHubEvent payloads.

    We should run regular updates for daily events but once a day has passed we
    should never need to update it.
    """

    date = models.DateField(db_index=True)

    total_opened = models.IntegerField()
    total_merged = models.IntegerField()
    total_closed = models.IntegerField()

    kodiak_approved = models.IntegerField()
    kodiak_merged = models.IntegerField()
    kodiak_updated = models.IntegerField()

    github_installation_id = models.IntegerField(db_index=True)

    class Meta:
        db_table = "pull_request_activity"
        # we should only have one set of totals per account, per day.
        constraints = [
            models.UniqueConstraint(
                fields=["date", "github_installation_id"],
                name="unique_pull_request_activity",
            )
        ]

    __repr__ = sane_repr(
        "date",
        "total_opened",
        "total_merged",
        "total_closed",
        "kodiak_approved",
        "kodiak_merged",
        "kodiak_updated",
        "github_installation_id",
    )

    @staticmethod
    def generate_activity_data(
        min_date: Optional[datetime.date] = None, account: Optional[Account] = None
    ) -> None:
        """
        Generate/update PullRequestActivity using data from the GitHubEvent table.
        """
        where_clause = []
        if min_date is not None:
            where_clause.append(f"created_at > '{min_date.isoformat()}'::date")
        if account is not None:
            where_clause.append(
                f"(payload -> 'installation' ->> 'id')::integer = {account.github_installation_id}"
            )
        if where_clause:
            where = " WHERE " + " AND ".join(where_clause)
        else:
            where = ""
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
INSERT INTO pull_request_activity (
    "id",
    "created_at",
    "modified_at",
    "date",
    "github_installation_id",
    kodiak_updated,
    kodiak_merged,
    kodiak_approved,
    "total_opened",
    "total_merged",
    total_closed)
SELECT
    uuid_generate_v4 () "id",
    NOW() created_at,
    NOW() modified_at,
    created_at::date "date",
    (payload -> 'installation' ->> 'id')::integer github_installation_id,
sum(
    CASE WHEN (event_name = 'pull_request'
        AND payload -> 'sender' ->> 'login' LIKE 'kodiak%[bot]'
        AND payload ->> 'action' = 'synchronize') THEN
        1
    ELSE
        0
    END) kodiak_updated,
sum(
    CASE WHEN (event_name = 'pull_request'
        AND payload -> 'sender' ->> 'login' LIKE 'kodiak%[bot]'
        AND payload ->> 'action' = 'closed'
        AND payload -> 'pull_request' -> 'merged' = to_jsonb (TRUE)) THEN
        1
    ELSE
        0
    END) kodiak_merged,
sum(
    CASE WHEN (event_name = 'pull_request_review'
        AND payload -> 'sender' ->> 'login' LIKE 'kodiak%[bot]') THEN
        1
    ELSE
        0
    END) kodiak_approved,
sum(
    CASE WHEN (event_name = 'pull_request'
        AND payload ->> 'action' = 'opened') THEN
        1
    ELSE
        0
    END) total_opened,
sum(
    CASE WHEN (event_name = 'pull_request'
        AND payload ->> 'action' = 'closed'
        AND payload -> 'pull_request' -> 'merged' = to_jsonb (TRUE)) THEN
        1
    ELSE
        0
    END) total_merged,
sum(
    CASE WHEN (event_name = 'pull_request'
        AND payload ->> 'action' = 'closed'
        AND payload -> 'pull_request' -> 'merged' = to_jsonb (FALSE)) THEN
        1
    ELSE
        0
    END) total_closed
FROM
    github_event

{where}

GROUP BY
    (payload -> 'installation' ->> 'id')::integer,
    created_at::date
ON CONFLICT ON CONSTRAINT unique_pull_request_activity
DO UPDATE
    SET
        kodiak_updated = excluded.kodiak_updated,
        kodiak_merged = excluded.kodiak_merged,
        kodiak_approved = excluded.kodiak_approved,
        total_opened = excluded.total_opened,
        total_merged = excluded.total_merged,
        total_closed = excluded.total_closed;
"""
            )


class PullRequestActivityProgress(BaseModel):
    """
    Store information about PullRequestActivity generation.

    We only want to generate PullRequestActivity for new/incomplete days. If a
    day has already passed, recalculating analytics for it would not be useful
    work. By tracking our progress we can avoid work.
    """

    min_date = models.DateField(
        help_text="Date we should use as our minimum date for future aggregation jobs. Anything before this date is 'locked'."
    )

    class Meta:
        db_table = "pull_request_activity_progress"


@dataclass
class ActiveUser:
    github_login: str
    github_id: int
    days_active: int
    last_active_at: datetime.date

    def profile_image(self) -> str:
        return f"https://avatars.githubusercontent.com/u/{self.github_id}"


class UserPullRequestActivity(BaseModel):
    """
    Stores a record of GitHub user activity on a pull request on a day.
    """

    github_installation_id = models.IntegerField(db_index=True)
    github_repository_name = models.CharField(max_length=255, db_index=True)
    github_pull_request_number = models.IntegerField(db_index=True)
    github_user_login = models.CharField(max_length=255, db_index=True)
    github_user_id = models.IntegerField(db_index=True)
    is_private_repository = models.BooleanField(db_index=True)
    activity_date = models.DateField(db_index=True)

    class Meta:
        db_table = "user_pull_request_activity"
        # we should have one event per user, per pull request, per repository,
        # per installation, per day.
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "github_installation_id",
                    "github_repository_name",
                    "github_pull_request_number",
                    "github_user_id",
                    "activity_date",
                ],
                name="unique_user_pull_request_activity",
            )
        ]

    @staticmethod
    def get_active_users_in_last_30_days(account: Account):
        with connection.cursor() as cursor:
            cursor.execute(
                """
            SELECT
                max(a.github_user_login) github_user_login,
                a.github_user_id,
                count(distinct a.activity_date) days_active,
                max(a.activity_date) last_active_at
            FROM
                user_pull_request_activity a
                JOIN user_pull_request_activity b ON a.github_installation_id = b.github_installation_id
                    AND a.github_repository_name = b.github_repository_name
                    AND a.github_pull_request_number = b.github_pull_request_number
            WHERE
                b.github_user_login LIKE 'kodiak%%[bot]'
                AND a.github_user_login NOT LIKE '%%[bot]'
                AND a.activity_date > now() - '30 days'::interval
                AND b.activity_date > now() - '30 days'::interval
                AND a.is_private_repository = TRUE
                AND b.is_private_repository = TRUE
                AND a.github_installation_id = %s
            GROUP BY
                a.github_user_id;
            """,
                [account.github_installation_id],
            )
            results = cursor.fetchall()
        return [
            ActiveUser(
                github_login=github_login,
                github_id=github_id,
                days_active=days_active,
                last_active_at=last_active_at,
            )
            for github_login, github_id, days_active, last_active_at in results
        ]

    @staticmethod
    def generate() -> None:
        """
        Find all pull requests acted on by Kodiak.
        """
        user_pull_request_activity_progress: Optional[
            UserPullRequestActivityProgress
        ] = UserPullRequestActivityProgress.objects.order_by("-min_date").first()
        where_clause = []
        if user_pull_request_activity_progress is not None:
            where_clause.append(
                f"created_at > '{user_pull_request_activity_progress.min_date.isoformat()}'::timestamp"
            )

        if where_clause:
            where = " AND " + " AND ".join(where_clause)
        else:
            where = ""
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
INSERT INTO user_pull_request_activity (
    "id",
    "created_at",
    "modified_at",
    "github_installation_id",
    "github_repository_name",
    "github_pull_request_number",
    "github_user_login",
    "github_user_id",
    "is_private_repository",
    "activity_date")
SELECT
    uuid_generate_v4 () "id",
    NOW() created_at,
    NOW() modified_at,
    (payload -> 'installation' ->> 'id')::int github_installation_id,
    (payload -> 'repository' ->> 'name') github_repository_name,
    (payload -> 'pull_request' ->> 'number')::int github_pull_request_number,
    max(payload -> 'sender' ->> 'login') github_user_login,
    (payload -> 'sender' ->> 'id')::integer github_user_id,
    (payload -> 'repository' ->> 'private')::boolean is_private_repository,
    created_at::date activity_date
FROM
    github_event
WHERE
    event_name in ('pull_request', 'pull_request_review')
    {where}
GROUP BY
    github_installation_id,
    github_repository_name,
    github_pull_request_number,
    github_user_id,
    is_private_repository,
    activity_date;
"""
            )
        UserPullRequestActivityProgress.objects.create(min_date=timezone.now())


class UserPullRequestActivityProgress(BaseModel):
    min_date = models.DateTimeField(
        help_text="Date we should use as our minimum date for future aggregation jobs. Anything before this date is 'locked'.",
        db_index=True,
    )

    class Meta:
        db_table = "user_pull_request_activity_progress"
