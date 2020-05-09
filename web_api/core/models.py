from __future__ import annotations

import datetime
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Callable, List, Optional, cast

import pydantic
import redis
import requests
import stripe
from django.conf import settings
from django.contrib.postgres import fields as pg_fields
from django.db import connection, models
from django.utils import timezone
from typing_extensions import Literal

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY
r = redis.Redis.from_url(settings.REDIS_URL)


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

    __str__ = __repr__


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

    def can_edit(self, account: Account) -> bool:
        return cast(
            bool,
            AccountMembership.objects.filter(
                account=account, user=self, role=AccountRole.admin
            ).exists(),
        )

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
            if installation_account_type == "Organization":
                account_membership_res = requests.get(
                    f"https://api.github.com/orgs/{installation_account_login}/memberships/{self.github_login}",
                    headers=dict(authorization=f"Bearer {self.github_access_token}"),
                    timeout=5,
                )
                account_membership_res.raise_for_status()
                role = account_membership_res.json()["role"]
            elif (
                installation_account_type == "User"
                and installation_account_login == self.github_login
            ):
                role = "admin"
            else:
                role = "member"

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
                account_membership = AccountMembership.objects.get(
                    account=account, user=self
                )
                account_membership.role = role
                account_membership.save()
            except AccountMembership.DoesNotExist:
                AccountMembership.objects.create(account=account, user=self, role=role)

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


class AccountType(models.TextChoices):
    user = "User"
    organization = "Organization"


class Account(BaseModel):
    """
    An GitHub Kodiak App installation for a GitHub organization or user.

    Users are associated with Accounts via AccountMembership.
    """

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
    trial_expiration = models.DateTimeField(null=True)
    trial_start = models.DateTimeField(null=True)
    trial_started_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    trial_email = models.CharField(blank=True, max_length=255)

    stripe_customer_id = models.CharField(
        blank=True,
        max_length=255,
        db_index=True,
        help_text="ID of the Stripe Customer associated with this account. This will have a corresponding object in StripeCustomerInformation if the user has created a subscription.",
    )

    class Meta:
        db_table = "account"
        constraints = [
            models.CheckConstraint(
                check=models.Q(github_account_type__in=AccountType.values),
                name="github_account_type_valid",
            )
        ]

    __repr__ = sane_repr(
        "github_installation_id", "github_account_id", "github_account_login"
    )

    def profile_image(self) -> str:
        return f"https://avatars.githubusercontent.com/u/{self.github_account_id}"

    def stripe_customer_info(self) -> Optional[StripeCustomerInformation]:
        return cast(
            Optional[StripeCustomerInformation],
            StripeCustomerInformation.objects.filter(
                customer_id=self.stripe_customer_id
            ).first(),
        )

    def start_trial(
        self, actor: User, billing_email: str, length_days: int = 30
    ) -> None:
        """
        Start the timer for the trial and create a Stripe customer.

        If the trial already exists, we only update the email if provided. We
        also update the Stripe customer email.
        """
        self.trial_email = billing_email
        if self.trial_expiration is None:
            self.trial_expiration = timezone.now() + datetime.timedelta(
                days=length_days
            )
            self.trial_start = timezone.now()
            self.trial_started_by = actor
        else:
            logger.warning("attempted to start trial when one already exists")
        if not self.stripe_customer_id:
            customer = stripe.Customer.create(email=billing_email)
            self.stripe_customer_id = customer.id
        else:
            stripe.Customer.modify(self.stripe_customer_id, email=billing_email)
        self.save()
        self.update_bot()

    def trial_expired(self) -> bool:
        return self.trial_expiration is not None and cast(
            bool, (self.trial_expiration - timezone.now()).total_seconds() < 0
        )

    def active_trial(self) -> bool:
        return self.trial_expiration is not None and cast(
            bool, (self.trial_expiration - timezone.now()).total_seconds() > 0
        )

    def get_active_user_count(self) -> int:
        return len(
            UserPullRequestActivity.get_active_users_in_last_30_days(account=self)
        )

    def get_subscription_blocker(
        self,
    ) -> Optional[Literal["subscription_expired", "trial_expired", "seats_exceeded"]]:
        """
        If there is a valid trial or subscription, we should return None. Otherwise we should return the reason for the block.
        """
        if self.github_account_type == AccountType.user:
            return None

        if self.active_trial():
            return None

        customer_info = self.stripe_customer_info()

        subscription_quantity = (
            customer_info.subscription_quantity if customer_info else 0
        )
        if subscription_quantity < self.get_active_user_count():
            return "seats_exceeded"

        if customer_info:
            if customer_info.expired:
                return "subscription_expired"
            # active subscription within active user limits.
            return None

        if self.trial_expired():
            return "trial_expired"

        # the user has never signed up for a trial or subscription and has 0
        # active users.
        return None

    def update_from(self, customer: stripe.Customer) -> None:
        self.stripe_customer_id = customer.id
        self.save()

    def update_bot(self) -> None:
        """
        Refresh subscription information in Redis for GitHub bot to load.
        """
        key = f"kodiak:subscription:{self.github_installation_id}".encode()

        r.hset(key, b"account_id", str(self.id))  # type: ignore
        subscription_blocker = self.get_subscription_blocker() or ""
        r.hset(key, b"subscription_blocker", subscription_blocker.encode())  # type: ignore

        # Trigger bot to reevaluate pull request mergeability.
        # We can use this to trigger the bot to remove the paywall status message on upgrades.

        class RefreshPullRequestsMessage(pydantic.BaseModel):
            installation_id: str

        r.rpush(
            "kodiak:refresh_pull_requests_for_installation",
            RefreshPullRequestsMessage(
                installation_id=self.github_installation_id
            ).json(),
        )


class AccountRole(models.TextChoices):
    admin = "admin"
    member = "member"


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
    role = models.CharField(
        max_length=255,
        choices=AccountRole.choices,
        help_text="User's GitHub-defined role for the associated account.",
    )

    class Meta:
        db_table = "account_membership"
        constraints = [
            models.CheckConstraint(
                check=models.Q(role__in=AccountRole.values), name="role_valid",
            )
        ]

    __repr__ = sane_repr("account_id", "user_id", "role")


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
    def aggregate_events() -> None:
        """
        Create PullRequestActivity objects from GitHubEvent information.
        """
        start_time = time.time()
        pr_progress: Optional[
            PullRequestActivityProgress
        ] = PullRequestActivityProgress.objects.order_by("-min_date").first()
        if pr_progress:
            min_date = timezone.make_aware(
                datetime.datetime(
                    pr_progress.min_date.year,
                    pr_progress.min_date.month,
                    pr_progress.min_date.day,
                )
            )
            events_aggregated = GitHubEvent.objects.filter(
                created_at__gte=min_date
            ).count()
        else:
            min_date = None
            events_aggregated = GitHubEvent.objects.count()
        new_min_date = datetime.date.today()
        PullRequestActivity.generate_activity_data(min_date=min_date)
        PullRequestActivityProgress.objects.create(min_date=new_min_date)
        logger.info(
            "generate_activity_data events_aggregated=%s min_date=%s new_min_date=%s duration_seconds=%s",
            events_aggregated,
            min_date,
            new_min_date,
            time.time() - start_time,
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
    opened_pull_request = models.BooleanField(db_index=True)
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
    def get_active_users_in_last_30_days(account: Account) -> List[ActiveUser]:
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
                -- We only consider users that open pull requests.
                -- For table b we look at all pull request events for Kodiak to
                -- find all the PRs Kodiak has touched.
                AND a.opened_pull_request = TRUE
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
    "activity_date",
    "opened_pull_request")
SELECT
    uuid_generate_v4 () "id",
    NOW() created_at,
    NOW() modified_at,
    (payload -> 'installation' ->> 'id')::int github_installation_id,
    (payload -> 'repository' ->> 'name') github_repository_name,
    (payload -> 'pull_request' ->> 'number')::int github_pull_request_number,
    max(payload -> 'sender' ->> 'login') github_user_login,
    (payload -> 'sender' ->> 'id')::integer github_user_id,
    bool_or((payload -> 'repository' ->> 'private')::boolean) is_private_repository,
    created_at::date activity_date,
    bool_or(payload ->> 'action' = 'opened') opened_pull_request
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
    activity_date
HAVING (payload -> 'installation' ->> 'id')::int IS NOT NULL
    AND (payload -> 'repository' ->> 'name') IS NOT NULL
    AND (payload -> 'pull_request' ->> 'number')::int IS NOT NULL
    AND max(payload -> 'sender' ->> 'login') IS NOT NULL
    AND (payload -> 'sender' ->> 'id')::integer IS NOT NULL
ON CONFLICT ON CONSTRAINT unique_user_pull_request_activity
    DO UPDATE
        SET opened_pull_request = (excluded.opened_pull_request OR user_pull_request_activity.opened_pull_request),
        is_private_repository = (excluded.is_private_repository OR user_pull_request_activity.is_private_repository);
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


class StripeCustomerInformation(models.Model):
    customer_id = models.CharField(
        max_length=255,
        primary_key=True,
        unique=True,
        db_index=True,
        help_text="Unique identifier for Stripe Customer object.",
    )
    subscription_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique identifier for Stripe Subscription object.",
    )
    plan_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Unique identifier for Stripe Plan object.",
    )
    payment_method_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Unique identifier for Stripe PaymentMethod object.",
    )

    # https://stripe.com/docs/api/customers/object
    customer_email = models.CharField(
        max_length=255, help_text="The customer’s email address."
    )
    customer_balance = models.IntegerField(
        default=0,
        help_text="Current balance, if any, being stored on the customer. If negative, the customer has credit to apply to their next invoice. If positive, the customer has an amount owed that will be added to their next invoice. The balance does not refer to any unpaid invoices; it solely takes into account amounts that have yet to be successfully applied to any invoice. This balance is only taken into account as invoices are finalized.",
    )
    customer_created = models.IntegerField(
        help_text="Time at which the object was created. Measured in seconds since the Unix epoch."
    )

    # https://stripe.com/docs/api/payment_methods/object
    payment_method_card_brand = models.CharField(
        max_length=255,
        null=True,
        help_text="Card brand. Can be `amex`, `diners`, `discover`, `jcb`, `mastercard`, `unionpay`, `visa`, or `unknown`.",
    )
    payment_method_card_exp_month = models.CharField(
        null=True,
        help_text="Two-digit number representing the card’s expiration month.",
        max_length=255,
    )
    payment_method_card_exp_year = models.CharField(
        null=True,
        help_text="Four-digit number representing the card’s expiration year.",
        max_length=255,
    )
    payment_method_card_last4 = models.CharField(
        max_length=255, null=True, help_text="The last four digits of the card."
    )

    # https://stripe.com/docs/api/plans/object
    plan_amount = models.IntegerField(
        help_text="The amount in cents to be charged on the interval specified."
    )

    # https://stripe.com/docs/api/subscriptions/object
    subscription_quantity = models.IntegerField(
        help_text="The quantity of the plan to which the customer is subscribed. For example, if your plan is $10/user/month, and your customer has 5 users, you could pass 5 as the quantity to have the customer charged $50 (5 x $10) monthly. Only set if the subscription contains a single plan."
    )
    subscription_start_date = models.IntegerField(
        help_text="Date when the subscription was first created. The date might differ from the created date due to backdating."
    )
    subscription_current_period_end = models.IntegerField(
        help_text="End of the current period that the subscription has been invoiced for. At the end of this period, a new invoice will be created."
    )
    subscription_current_period_start = models.IntegerField(
        help_text="Start of the current period that the subscription has been invoiced for."
    )

    class Meta:
        db_table = "stripe_customer_information"

    def update_from(
        self,
        subscription: stripe.Subscription,
        customer: stripe.Customer,
        payment_method: stripe.PaymentMethod,
    ) -> None:

        self.subscription_id = subscription.id
        self.plan_id = subscription.plan.id
        self.payment_method_id = payment_method.id

        self.customer_email = customer.email
        self.customer_balance = customer.balance
        self.customer_created = customer.created

        self.payment_method_card_brand = payment_method.card.brand
        self.payment_method_card_exp_month = payment_method.card.exp_month
        self.payment_method_card_exp_year = payment_method.card.exp_year
        self.payment_method_card_last4 = payment_method.card.last4

        self.plan_amount = subscription.plan.amount

        self.subscription_quantity = subscription.quantity
        self.subscription_start_date = subscription.start_date
        self.subscription_current_period_end = subscription.current_period_end
        self.subscription_current_period_start = subscription.current_period_start
        self.save()
        self.get_account().update_bot()

    def get_account(self) -> Account:
        return cast(Account, Account.objects.get(stripe_customer_id=self.customer_id))

    @property
    def expired(self) -> bool:
        # provide two days of leeway for good measure
        two_days = 60 * 60 * 24 * 2
        now = int(time.time())
        return cast(bool, now > (self.subscription_current_period_end + two_days))

    @property
    def next_billing_date(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(self.subscription_current_period_end)

    def cancel_subscription(self) -> None:
        """
        Cancel the Account's subscription in Stripe and remove the
        StripeCustomerInformation object.
        """
        # Calling delete on a subscription cancels it. If a user wants to
        # resubscribe they must create a new subscription.
        # https://stripe.com/docs/billing/subscriptions/canceling
        stripe.Subscription.delete(self.subscription_id)
        # we delete all the associated subscription info because the
        # subscription is no longer valid. We leave the Stripe Customer and keep
        # Account.customer_id alone. If a user resubscribes we can use their
        # existing Stripe Customer to improve their Stripe Checkout flow with a
        # prefilled email.
        account = self.get_account()
        self.delete()
        account.update_bot()

    def preview_proration(self, *, timestamp: int, subscription_quantity: int) -> int:
        proration_date = timestamp

        subscription = stripe.Subscription.retrieve(self.subscription_id)

        # See what the next invoice would look like with a plan switch
        # and proration set:
        subscription_items = [
            {
                "id": subscription["items"]["data"][0].id,
                "quantity": subscription_quantity,
            }
        ]

        invoice = stripe.Invoice.upcoming(
            customer=self.customer_id,
            subscription=self.subscription_id,
            subscription_items=subscription_items,
            subscription_proration_date=proration_date,
        )

        # Calculate the proration cost:

        return sum(
            proration.amount
            for proration in invoice.lines.data
            if proration.period.start - proration_date <= 1
        )
