from functools import wraps
from typing import Callable, cast

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse

from core.models import AnonymousUser, User


def login_required(view_func: Callable) -> Callable:
    @wraps(view_func)
    def wrapped_view(
        request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        raise PermissionDenied("authentication required")

    return wrapped_view


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
        request._cached_user = user or AnonymousUser()
    return cast(User, request._cached_user)


def login(user: User, request: HttpRequest) -> None:
    """
    https://github.com/django/django/blob/6e99585c19290fb9bec502cac8210041fdb28484/django/contrib/auth/__init__.py#L86-L131
    """
    request.session["user_id"] = str(user.id)
    request.user = user


def logout(request: HttpRequest) -> None:
    """
    https://github.com/django/django/blob/6e99585c19290fb9bec502cac8210041fdb28484/django/contrib/auth/__init__.py#L134-L148
    """
    request.session.flush()
    request.user = AnonymousUser()
