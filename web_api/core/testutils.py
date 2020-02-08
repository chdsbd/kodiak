from importlib import import_module

from django.conf import settings
from django.contrib.sessions.backends.base import SessionBase as SessionStore
from django.http import HttpRequest, SimpleCookie
from django.test.client import Client as DjangoTestClient

from core import auth
from core.models import User


class TestClient(DjangoTestClient):
    def login(self, user: User) -> None:
        engine: SessionStore = import_module(settings.SESSION_ENGINE)

        # Create a fake request to store login details.
        request = HttpRequest()

        if self.session:
            request.session = self.session
        else:
            request.session = engine.SessionStore()
        auth.login(user, request)

        # Save the session values.
        request.session.save()

        # Set the cookie to represent the session.
        session_cookie = settings.SESSION_COOKIE_NAME
        self.cookies[session_cookie] = request.session.session_key
        cookie_data = {
            "max-age": None,
            "path": "/",
            "domain": settings.SESSION_COOKIE_DOMAIN,
            "secure": settings.SESSION_COOKIE_SECURE or None,
            "expires": None,
        }
        self.cookies[session_cookie].update(cookie_data)

    def logout(self) -> None:
        """Log out the user by removing the cookies and session object."""
        request = HttpRequest()
        engine: SessionStore = import_module(settings.SESSION_ENGINE)
        if self.session:
            request.session = self.session
            request.user = auth.get_user(request)
        else:
            request.session = engine.SessionStore()
        auth.logout(request)
        self.cookies = SimpleCookie()
