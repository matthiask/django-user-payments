from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone
from django.utils.translation import deactivate_all

from user_payments.models import LineItem, Payment
from user_payments.user_subscriptions.models import Subscription, SubscriptionPeriod


class Test(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser("admin", "admin@test.ch", "blabla")
        deactivate_all()

    def login(self):
        client = Client()
        client.force_login(self.user)
        return client

    def test_model(self):
        subscription = Subscription.objects.create(
            user=self.user,
            code="test1",
            title="Test subscription 1",
            periodicity="monthly",
            amount=60,
            starts_on=date(2040, 1, 1),
        )

        self.assertEqual(SubscriptionPeriod.objects.count(), 0)
        Subscription.objects.create_periods()
        self.assertEqual(SubscriptionPeriod.objects.count(), 0)

        subscription.create_periods(until=date(2040, 3, 31))

        self.assertEqual(SubscriptionPeriod.objects.count(), 3)
        self.assertEqual(LineItem.objects.count(), 0)

        SubscriptionPeriod.objects.create_line_items()
        self.assertEqual(LineItem.objects.count(), 3)

        payment = Payment.objects.create_pending(user=self.user)
        self.assertEqual(payment.amount, 180)

        subscription.create_periods(until=date(2040, 4, 1))
        self.assertEqual(SubscriptionPeriod.objects.count(), 4)

        subscription.refresh_from_db()
        # Not paid yet.
        self.assertEqual(subscription.paid_until, date(2040, 1, 1))

        payment.charged_at = timezone.now()
        payment.save()

        subscription.refresh_from_db()
        self.assertEqual(subscription.paid_until, date(2040, 1, 1))

        subscription.update_paid_until()  # XXX call automatically?
        self.assertEqual(subscription.paid_until, date(2040, 3, 31))
