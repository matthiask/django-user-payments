from user_payments.management.base import OptionalRavenCommand
from user_payments.user_subscriptions.models import Subscription, SubscriptionPeriod


class Command(OptionalRavenCommand):
    help = "Generate subscription periods and user payments line items"

    def _handle(self, **options):
        Subscription.objects.disable_autorenewal()
        Subscription.objects.create_periods()
        SubscriptionPeriod.objects.create_line_items()
