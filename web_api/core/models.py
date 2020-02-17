import datetime
import logging
import uuid
from typing import List, Optional

import requests
from django.contrib.postgres import fields as pg_fields
from django.db import connection, models

logger = logging.getLogger(__name__)


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


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


class PullRequestActivity(BaseModel):
    """
    Store a per-day aggregate of pull request activity.

    This information is calculated in the background from GitHubEvent payloads.

    We should run regular updates for daily events but once a day has passed we
    should never need to update it.
    """

    date = models.DateField()

    total_opened = models.IntegerField()
    total_merged = models.IntegerField()
    total_closed = models.IntegerField()

    kodiak_approved = models.IntegerField()
    kodiak_merged = models.IntegerField()
    kodiak_updated = models.IntegerField()

    account = models.ForeignKey(
        Account,
        to_field="github_installation_id",
        db_column="github_installation_id",
        db_constraint=False,
        on_delete=models.CASCADE,
    )

    class Meta:
        db_table = "pull_request_activity"
        # we should only have one set of totals per account, per day.
        constraints = [
            models.UniqueConstraint(
                fields=["date", "account"], name="unique_pull_request_activity"
            )
        ]

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
        AND payload -> 'action' = to_jsonb ('synchronize'::text)) THEN
        1
    ELSE
        0
    END) kodiak_updated,
sum(
    CASE WHEN (event_name = 'pull_request'
        AND payload -> 'sender' ->> 'login' LIKE 'kodiak%[bot]'
        AND payload -> 'action' = to_jsonb ('closed'::text)
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
        AND payload -> 'action' = to_jsonb ('opened'::text)) THEN
        1
    ELSE
        0
    END) total_opened,
sum(
    CASE WHEN (event_name = 'pull_request'
        AND payload -> 'action' = to_jsonb ('closed'::text)
        AND payload -> 'pull_request' -> 'merged' = to_jsonb (TRUE)) THEN
        1
    ELSE
        0
    END) total_merged,
sum(
    CASE WHEN (event_name = 'pull_request'
        AND payload -> 'action' = to_jsonb ('closed'::text)
        AND payload -> 'pull_request' -> 'merged' = to_jsonb (FALSE)) THEN
        1
    ELSE
        0
    END) total_closed
FROM
    github_event

{where}

GROUP BY
    payload -> 'installation' ->> 'id',
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
