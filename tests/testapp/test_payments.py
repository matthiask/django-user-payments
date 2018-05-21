from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone
from django.utils.translation import deactivate_all

from user_payments.models import LineItem, Payment


class Test(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser("admin", "admin@test.ch", "blabla")
        deactivate_all()

    def login(self):
        client = Client()
        client.force_login(self.user)
        return client

    def test_model(self):
        self.assertEqual(Payment.objects.create_pending(user=self.user), None)

        LineItem.objects.create(user=self.user, amount=5, title="Something")

        payment = Payment.objects.create_pending(user=self.user)

        self.assertEqual(payment.email, "admin@test.ch")
        self.assertEqual(payment.amount, 5)
        self.assertEqual(
            payment.description, "Payment of 5.00 by admin@test.ch: Something"
        )
        self.assertEqual(str(payment), "Pending payment of 5.00")

        self.assertEqual(LineItem.objects.unbound().count(), 0)
        self.assertEqual(LineItem.objects.unpaid().count(), 1)

        payment.cancel_pending()

        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(LineItem.objects.unbound().count(), 1)
        self.assertEqual(LineItem.objects.unpaid().count(), 1)

        payment = Payment.objects.create_pending(
            user=self.user, email="test@example.org"
        )

        # Overridden email address:
        self.assertEqual(payment.email, "test@example.org")

        payment.charged_at = timezone.now()
        payment.save()

        self.assertEqual(LineItem.objects.unbound().count(), 0)
        self.assertEqual(LineItem.objects.unpaid().count(), 0)
        self.assertEqual(str(payment), "Payment of 5.00")
