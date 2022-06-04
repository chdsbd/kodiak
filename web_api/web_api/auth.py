from __future__ import annotations

from functools import wraps
from typing import Any, TypeVar, Union, cast

from django.http import HttpRequest, HttpResponse
from typing_extensions import Protocol

from web_api.exceptions import AuthenticationRequired
from web_api.models import AnonymousUser, User


class AuthedHttpRequest(HttpRequest):
    user: User  # type: ignore [assignment]


class RequestHandler1(Protocol):
    def __call__(self, request: AuthedHttpRequest) -> HttpResponse:
        ...


class RequestHandler2(Protocol):
    def __call__(self, request: AuthedHttpRequest, __arg1: Any) -> HttpResponse:
        ...


RequestHandler = Union[RequestHandler1, RequestHandler2]


# Verbose bound arg due to limitations of Python typing.
# see: https://github.com/python/mypy/issues/5876
_F = TypeVar("_F", bound=RequestHandler)


def login_required(view_func: _F) -> _F:
    @wraps(view_func)
    def wrapped_view(
        request: AuthedHttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        raise AuthenticationRequired

    return cast(_F, wrapped_view)


def get_user(request: HttpRequest) -> User:
    """
    Get a `User` from the request. If the user cannot be found we return `AnonymousUser`.

    Modified from: https://github.com/django/django/blob/6e99585c19290fb9bec502cac8210041fdb28484/django/contrib/auth/middleware.py#L9-L12
    """
    if not hasattr(request, "_cached_user"):
        user = None
        try:
            user_id = request.session["user_id"]
        except KeyError:
            pass
        else:
            user = User.objects.filter(id=user_id).first()
        request._cached_user = user or AnonymousUser()  # type: ignore [attr-defined]
    return request._cached_user  # type: ignore [attr-defined, no-any-return]


def login(user: User, request: HttpRequest) -> None:
    """
    https://github.com/django/django/blob/6e99585c19290fb9bec502cac8210041fdb28484/django/contrib/auth/__init__.py#L86-L131
    """
    request.session["user_id"] = str(user.id)
    request.user = user  # type: ignore [assignment]


def logout(request: HttpRequest) -> None:
    """
    https://github.com/django/django/blob/6e99585c19290fb9bec502cac8210041fdb28484/django/contrib/auth/__init__.py#L134-L148
    """
    request.session.flush()
    request.user = AnonymousUser()  # type: ignore [assignment]
