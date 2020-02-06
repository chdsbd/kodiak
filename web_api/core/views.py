from typing import Callable
from django.http import JsonResponse, HttpResponse, HttpRequest
import datetime
from django.core.exceptions import PermissionDenied
from functools import wraps
from core.models import User, AnonymousUser


def login_required(view_func: Callable) -> Callable:
    @wraps(view_func)
    def wrapped_view(
        request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        raise PermissionDenied("authentication required")

    return wrapped_view


def current_datetime(request: HttpRequest) -> HttpResponse:
    now = datetime.datetime.now()
    html = "<html><body>It is now %s.</body></html>" % now
    return HttpResponse(html)


def hello(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"hello": 123})


@login_required
def installations(request: HttpRequest) -> JsonResponse:
    return JsonResponse([{"id": 53121}], safe=False)


def login(request: HttpRequest) -> JsonResponse:
    u = User.objects.get(github_login=request.POST["github_login"])
    request.session["user_id"] = str(u.id)
    return JsonResponse(
        {
            "OK": True,
            "id": u.id,
            "github_id": u.github_id,
            "github_login": u.github_login,
            "created_at": u.created_at,
            "modified_at": u.modified_at,
        }
    )


def logout(request: HttpRequest) -> JsonResponse:
    request.session.flush()
    request.user = AnonymousUser()
    return HttpResponse(status=201)
