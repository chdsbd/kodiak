from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject

from core.models import User

def get_user(request):
    if not hasattr(request, '_cached_user'):
        request._cached_user = User.objects.from_request(request=request)
    return request._cached_user


class AuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.user = SimpleLazyObject(lambda: get_user(request))
