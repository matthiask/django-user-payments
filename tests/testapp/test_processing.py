from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.utils.translation import deactivate_all

import stripe
from user_payments.models import LineItem, Payment
from user_payments.processing import process_unbound_items, process_pending_payments
from user_payments.stripe_customers.models import Customer


class Test(TestCase):
    def setUp(self):
        deactivate_all()

    def test_processing(self):
        item = LineItem.objects.create(
            user=User.objects.create(username="test1", email="test1@example.com"),
            amount=5,
            title="Stuff",
        )

        Customer.objects.create(
            user=item.user, customer_id="cus_example", customer_data="{}"
        )

        LineItem.objects.create(
            user=User.objects.create(username="test2", email="test2@example.com"),
            amount=10,
            title="Other stuff",
        )

        with mock.patch.object(stripe.Charge, "create", return_value={"success": True}):
            process_unbound_items()

        self.assertEqual(len(mail.outbox), 1)

        self.assertEqual(LineItem.objects.unbound().count(), 1)
        self.assertEqual(LineItem.objects.unpaid().count(), 1)

        payment = Payment.objects.get()
        self.assertTrue(payment.charged_at is not None)
        self.assertEqual(payment.user, item.user)

    def test_card_error(self):
        item = LineItem.objects.create(
            user=User.objects.create(username="test1", email="test1@example.com"),
            amount=5,
            title="Stuff",
        )
        Customer.objects.create(
            user=item.user, customer_id="cus_example", customer_data="{}"
        )

        with mock.patch.object(
            stripe.Charge,
            "create",
            side_effect=stripe.CardError("problem", "param", "code"),
        ):
            process_unbound_items()

        item = LineItem.objects.get()

        self.assertTrue(item.payment is None)
        self.assertEqual(Payment.objects.count(), 0)

        # Card error mail, please pay mail
        self.assertEqual(len(mail.outbox), 2)

    def test_pending_payments(self):
        item = LineItem.objects.create(
            user=User.objects.create(username="test1", email="test1@example.com"),
            amount=5,
            title="Stuff",
        )

        Payment.objects.create_pending(user=item.user)

        process_pending_payments()

        self.assertEqual(len(mail.outbox), 1)

        self.assertEqual(LineItem.objects.unbound().count(), 0)
        self.assertEqual(LineItem.objects.unpaid().count(), 1)

        payment = Payment.objects.get()
        self.assertTrue(payment.charged_at is None)

    def test_process_payment_exception(self):
        item = LineItem.objects.create(
            user=User.objects.create(username="test1", email="test1@example.com"),
            amount=5,
            title="Stuff",
        )
        Customer.objects.create(
            user=item.user, customer_id="cus_example", customer_data="{}"
        )
        Payment.objects.create_pending(user=item.user)

        class SomeException(Exception):
            pass

        with self.assertRaises(SomeException):
            with mock.patch.object(
                stripe.Charge,
                "create",
                side_effect=SomeException(),  # Just not a stripe.CardError
            ):
                process_pending_payments()
