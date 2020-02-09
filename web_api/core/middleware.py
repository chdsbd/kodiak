from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject

from core.auth import get_user


class AuthenticationMiddleware(MiddlewareMixin):
    """
    Set the current `User` on the request at `request.user`

    If the user cannot be found from the request we set `request.user` to `AnonymousUser`.

    https://github.com/django/django/blob/6e99585c19290fb9bec502cac8210041fdb28484/django/contrib/auth/middleware.py#L15-L23
    """

    def process_request(self, request: HttpRequest) -> None:
        request.user = SimpleLazyObject(lambda: get_user(request))


class CORSMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        response["Access-Control-Allow-Origin"] = settings.KODIAK_WEB_APP_URL
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Headers"] = "content-type"

        return response
