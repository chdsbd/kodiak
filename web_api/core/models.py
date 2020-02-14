import uuid

from django.contrib.postgres import fields as pg_fields
from django.db import models


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(BaseModel):
    github_id = models.IntegerField()
    github_login = models.CharField(max_length=255)
    github_access_token = models.CharField(max_length=255)

    class Meta:
        db_table = "user"

    @property
    def is_authenticated(self) -> bool:
        return True


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
