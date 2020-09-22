from django.core.management.base import BaseCommand

from web_api.event_ingestion import ingest_events


class Command(BaseCommand):
    help = "Ingest webhook events into Postgres"

    def handle(self, *args, **options):
        ingest_events()
