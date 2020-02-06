from typing import cast
from django.http import HttpRequest
from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject

from core.models import User


def get_user(request: HttpRequest) -> User:
    if not hasattr(request, "_cached_user"):
        request._cached_user = User.objects.from_request(request=request)
    return cast(User, request._cached_user)


class AuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request: HttpRequest) -> None:
        request.user = SimpleLazyObject(lambda: get_user(request))
