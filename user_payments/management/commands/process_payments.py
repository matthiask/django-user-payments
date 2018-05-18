import logging

from django.core.management.base import BaseCommand

from user_payments.processors import process_unbound_items


class Command(BaseCommand):
    help = "Create pending payments from line items and try settling them"

    def handle(self, **options):
        logger = logging.getLogger("user_payments")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(logging.StreamHandler)

        process_unbound_items()
