import enum
import logging
from typing import Callable, Optional

import pydantic
from django.http import HttpRequest, HttpResponse, HttpResponseServerError, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject

from web_api.auth import get_user
from web_api.exceptions import ApiException

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(MiddlewareMixin):
    """
    Set the current `User` on the request at `request.user`

    If the user cannot be found from the request we set `request.user` to `AnonymousUser`.

    https://github.com/django/django/blob/6e99585c19290fb9bec502cac8210041fdb28484/django/contrib/auth/middleware.py#L15-L23
    """

    def process_request(self, request: HttpRequest) -> None:
        request.user = SimpleLazyObject(lambda: get_user(request))  # type: ignore [assignment]


class ExceptionMiddleware(MiddlewareMixin):
    def process_exception(
        self, request: HttpRequest, exception: Exception
    ) -> Optional[HttpResponse]:
        if isinstance(exception, ApiException):
            return JsonResponse(dict(message=exception.message), status=exception.code)
        # return a 400 response if we encounter a pydantic validation error.
        if isinstance(exception, pydantic.ValidationError):
            return JsonResponse(dict(message=exception.errors()), status=400)
        return None


@enum.unique
class ReadinessError(enum.Enum):
    PG_BAD_RESPONSE = "PG_BAD_RESPONSE"
    PG_CANNOT_CONNECT = "PG_CANNOT_CONNECT"


class HealthCheckMiddleware:
    """
    from: https://www.ianlewis.org/en/kubernetes-health-checks-django
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method == "GET":
            if request.path == "/readiness":
                return self.readiness(request)
            if request.path == "/healthz":
                return self.healthz(request)
        return self.get_response(request)

    def healthz(self, request: HttpRequest) -> HttpResponse:
        """
        Note: we don't check the database here because if the database
        connection failed then this service would restart, not the database.
        """
        return HttpResponse("OK")

    def readiness(self, request: HttpRequest) -> HttpResponse:
        """
        Connect to each database and do a generic standard SQL query
        that doesn't write any data and doesn't depend on any tables
        being present.
        """
        try:
            from django.db import connections  # pylint: disable=import-outside-toplevel

            for name in connections:
                cursor = connections[name].cursor()
                cursor.execute("SELECT 1;")
                row = cursor.fetchone()
                if row is None:
                    return HttpResponseServerError(ReadinessError.PG_BAD_RESPONSE)
        except Exception:  # noqa: PIE786
            logger.exception("could not connect to postgres")
            return HttpResponseServerError(ReadinessError.PG_CANNOT_CONNECT)

        return HttpResponse("OK")
