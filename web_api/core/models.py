import logging
import uuid
from typing import List, Optional

import requests
from django.contrib.postgres import fields as pg_fields
from django.db import models

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
    github_id = models.IntegerField(unique=True)
    github_login = models.CharField(unique=True, max_length=255)
    github_access_token = models.CharField(max_length=255)

    class Meta:
        db_table = "user"

    @property
    def is_authenticated(self) -> bool:
        return True

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
        )
        try:
            user_installations_res.raise_for_status()
        except requests.HTTPError:
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
                    github_id=installation_id,
                    github_account_id=installation_account_id,
                    github_account_login=installation_account_login,
                    github_account_type=installation_account_type,
                    payload=installation,
                )
            else:
                account = existing_account
                account.github_id = installation_id
                account.github_account_id = installation_account_id
                account.github_account_login = installation_account_login
                account.github_account_type = installation_account_type
                account.payload = installation
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
    class AccountType(models.TextChoices):
        user = "User"
        organization = "Organization"

    github_id = models.IntegerField(unique=True)
    github_account_id = models.IntegerField(unique=True)
    github_account_login = models.CharField(unique=True, max_length=255)
    github_account_type = models.CharField(max_length=255, choices=AccountType.choices)
    payload = pg_fields.JSONField(default=dict)

    class Meta:
        db_table = "account"


class AccountMembership(BaseModel):
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")

    class Meta:
        db_table = "account_membership"
