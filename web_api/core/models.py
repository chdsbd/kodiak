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


class SyncInstallationsError(Exception):
    pass


class User(BaseModel):
    github_id = models.IntegerField()
    github_login = models.CharField(max_length=255)
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
            raise SyncInstallationsError

        # TODO(chdsbd): Handle multiple pages of installations
        try:
            if user_installations_res.links["next"]:
                logging.warning("user has multiple pages")
        except KeyError:
            pass

        installations_data = user_installations_res.json()
        installations = installations_data["installations"]

        installs: List[Installation] = []

        for installation in installations:
            installation_id = installation["id"]
            installation_account_id = installation["account"]["id"]
            installation_account_login = installation["account"]["login"]
            installation_account_type = installation["account"]["type"]

            existing_install: Optional[Installation] = Installation.objects.filter(
                github_account_id=installation_account_id
            ).first()
            if existing_install is None:
                install = Installation.objects.create(
                    github_id=installation_id,
                    github_account_id=installation_account_id,
                    github_account_login=installation_account_login,
                    github_account_type=installation_account_type,
                    payload=installation,
                )
            else:
                install = existing_install
                install.github_id = installation_id
                install.github_account_id = installation_account_id
                install.github_account_login = installation_account_login
                install.github_account_type = installation_account_type
                install.payload = installation
                install.save()

            try:
                InstallationMembership.objects.get(installation=install, user=self)
            except InstallationMembership.DoesNotExist:
                InstallationMembership.objects.create(installation=install, user=self)

            installs.append(install)

        # remove installations to which the user no longer has access.
        InstallationMembership.objects.exclude(installation__in=installs).filter(
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


class Installation(BaseModel):
    class AccountType(models.TextChoices):
        user = "User"
        organization = "Organization"

    github_id = models.IntegerField(unique=True)
    github_account_id = models.IntegerField(unique=True)
    github_account_login = models.CharField(unique=True, max_length=255)
    github_account_type = models.CharField(max_length=255, choices=AccountType.choices)
    payload = pg_fields.JSONField(default=dict)

    class Meta:
        db_table = "installation"


class InstallationMembership(BaseModel):
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")

    class Meta:
        db_table = "installation_membership"
