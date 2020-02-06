from typing import Union
from django.http import HttpRequest
from django.db import models
import uuid


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserManager(models.Manager):
    def from_request(self, request: HttpRequest) -> Union["User", "AnonymousUser"]:
        """
        Return the user model instance associated with the given request session.
        If no user is retrieved, return an instance of `AnonymousUser`.
        """
        user = None
        try:
            user_id = request.session["user_id"]
        except KeyError:
            pass
        else:
            user = User.objects.filter(id=user_id).first()

        return user or AnonymousUser()


class User(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    github_id = models.IntegerField()
    github_login = models.CharField(max_length=255)
    github_access_token = models.CharField(max_length=255)

    class Meta:
        db_table = "user"

    objects = UserManager()

    @property
    def is_authenticated(self) -> bool:
        return True


class AnonymousUser:
    @property
    def is_authenticated(self) -> bool:
        return False
