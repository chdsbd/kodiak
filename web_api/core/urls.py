from django.urls import path

from core import views

urlpatterns = [
    path("oauth_login", views.oauth_login),
    path("oauth_callback", views.oauth_callback, name="oauth_callback"),
    path("logout", views.logout),
    path("installations", views.installations),
    path("ping", views.ping),
]
