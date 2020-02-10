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
