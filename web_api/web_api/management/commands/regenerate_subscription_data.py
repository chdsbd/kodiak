"""
Refresh all subscription settings via Stripe API
"""
from django.core.management.base import BaseCommand

from web_api.models import StripeCustomerInformation


class Command(BaseCommand):
    help = "Refresh subscription settings"

    def handle(self, *args: object, **options: object) -> None:
        for subscription in StripeCustomerInformation.objects.all():
            subscription.update_from_stripe()
