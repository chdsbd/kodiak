from django.urls import path

from web_api import views

urlpatterns = [
    path("v1/oauth_login", views.oauth_login),
    path("v1/oauth_complete", views.oauth_complete),
    path("v1/logout", views.logout),
    path("v1/sync_accounts", views.sync_accounts),
    path("v1/t/<uuid:team_id>/usage_billing", views.usage_billing),
    path("v1/t/<uuid:team_id>/activity", views.activity),
    path("v1/t/<uuid:team_id>/current_account", views.current_account),
    path("v1/t/<uuid:team_id>/start_trial", views.start_trial),
    path("v1/t/<uuid:team_id>/start_checkout", views.start_checkout),
    path(
        "v1/t/<uuid:team_id>/update_stripe_customer_info",
        views.update_stripe_customer_info,
    ),
    path("v1/t/<uuid:team_id>/subscription_info", views.get_subscription_info),
    path(
        "v1/t/<uuid:team_id>/stripe_self_serve_redirect",
        views.redirect_to_stripe_self_serve_portal,
    ),
    path("v1/stripe_webhook", views.stripe_webhook_handler),
    path("v1/accounts", views.accounts),
    path("v1/ping", views.ping),
    path("v1/healthcheck", views.healthcheck),
    path("v1/debug_sentry", views.debug_sentry),
]
