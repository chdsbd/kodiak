from django.core.management.base import BaseCommand

from core.models import UserPullRequestActivity


class Command(BaseCommand):
    help = "Generate User pull request activity analytics"

    def handle(self, *args, **options):
        UserPullRequestActivity.generate()
