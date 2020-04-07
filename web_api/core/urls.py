from django.urls import path

from core import views
from core.views import authentication as auth_views
from core.views import billing as billing_views

urlpatterns = [
    # auth views
    path("oauth_login", auth_views.oauth_login),
    path("oauth_complete", auth_views.oauth_complete),
    path("logout", auth_views.logout),
    path("sync_accounts", auth_views.sync_accounts),
    path("accounts", auth_views.accounts),
    # general views
    path("t/<uuid:team_id>/activity", views.activity),
    path("t/<uuid:team_id>/current_account", views.current_account),
    path("ping", views.ping),
    path("debug_sentry", views.debug_sentry),
    # blling views
    path("t/<uuid:team_id>/usage_billing", billing_views.usage_billing),
    path("t/<uuid:team_id>/start_trial", billing_views.start_trial),
    path("t/<uuid:team_id>/update_subscription", billing_views.update_subscription),
    path("t/<uuid:team_id>/fetch_proration", billing_views.fetch_proration),
    path("t/<uuid:team_id>/cancel_subscription", billing_views.cancel_subscription),
    path("t/<uuid:team_id>/start_checkout", billing_views.start_checkout),
    path(
        "t/<uuid:team_id>/modify_payment_details", billing_views.modify_payment_details
    ),
    path("stripe_webhook", billing_views.stripe_webhook_handler),
]
