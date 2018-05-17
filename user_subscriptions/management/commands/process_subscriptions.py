from django.core.management.base import BaseCommand

from user_subscriptions.models import Subscription, SubscriptionPeriod


class Command(BaseCommand):
    help = "Generate subscription periods and user payments line items"

    def handle(self, **options):
        Subscription.objects.create_periods()
        SubscriptionPeriod.objects.create_line_items()
