from django.core.management.base import BaseCommand

from core.models import UserPullRequestActivity


class Command(BaseCommand):
    help = "Generate User pull request activity analytics"

    def handle(self, *args, **options):
        UserPullRequestActivity.generate()


# TODO: Move all teh crons to management commands to pathing works prorperly!
