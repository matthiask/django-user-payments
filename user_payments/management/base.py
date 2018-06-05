from django.core.management.base import BaseCommand

try:
    from raven.contrib.django.raven_compat.models import client
except ImportError:
    client = None


class OptionalRavenCommand(BaseCommand):
    def handle(self, **options):
        if client is None:
            return self._handle(**options)

        try:
            return self._handle(**options)
        except Exception:
            client.captureException()
            raise
