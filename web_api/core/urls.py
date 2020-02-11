from django.urls import path

from core import views

urlpatterns = [
    path("oauth_login", views.oauth_login),
    path("oauth_complete", views.oauth_complete),
    path("logout", views.logout),
    path("installations", views.installations),
    path("usage_billing", views.usage_billing),
    path("activity", views.activity),
    path("ping", views.ping),
]
