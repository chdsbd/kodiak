from django.core.management.base import BaseCommand

from web_api.models import PullRequestActivity


class Command(BaseCommand):
    help = "Aggregate GitHubEvents into into PullRequestActivity"

    def handle(self, *args: object, **options: object) -> None:
        PullRequestActivity.aggregate_events()
