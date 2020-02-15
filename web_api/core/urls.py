from django.urls import path

from core import views

urlpatterns = [
    path("oauth_login", views.oauth_login),
    path("oauth_complete", views.oauth_complete),
    path("logout", views.logout),
    path("sync_accounts", views.sync_accounts),
    path("installations", views.installations),
    path("t/<uuid:team_id>/usage_billing", views.usage_billing),
    path("t/<uuid:team_id>/activity", views.activity),
    path("t/<uuid:team_id>/current_account", views.current_account),
    path("accounts", views.accounts),
    path("ping", views.ping),
]
