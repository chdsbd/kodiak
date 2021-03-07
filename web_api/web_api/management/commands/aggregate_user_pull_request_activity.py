from django.core.management.base import BaseCommand

from web_api.models import UserPullRequestActivity


class Command(BaseCommand):
    help = "Generate User pull request activity analytics"

    def handle(self, *args: object, **options: object) -> None:
        UserPullRequestActivity.generate()
