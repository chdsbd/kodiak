from django.core.management.base import BaseCommand

from core.models import PullRequestActivity


class Command(BaseCommand):
    help = "Aggregate GitHubEvents into into PullRequestActivity"

    def handle(self, *args, **options):
        PullRequestActivity.aggregate_events()
