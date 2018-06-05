import logging

from django.db import transaction

from user_payments.management.base import OptionalRavenCommand
from user_payments.processing import process_unbound_items, process_pending_payments


class Command(OptionalRavenCommand):
    help = "Create pending payments from line items and try settling them"

    def _handle(self, **options):
        logger = logging.getLogger("user_payments")
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        with transaction.atomic():
            process_unbound_items()
            process_pending_payments()
