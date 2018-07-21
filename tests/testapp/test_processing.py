from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.utils import timezone
from django.utils.translation import deactivate_all

import stripe
from user_payments.models import LineItem, Payment
from user_payments.processing import (
    Result,
    ResultError,
    process_payment,
    process_unbound_items,
    process_pending_payments,
)
from user_payments.stripe_customers.models import Customer

from testapp.processing import processors


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
            process_unbound_items(processors=processors)

        self.assertEqual(len(mail.outbox), 1)

        self.assertEqual(LineItem.objects.unbound().count(), 1)
        self.assertEqual(LineItem.objects.unpaid().count(), 1)

        payment = Payment.objects.get()
        self.assertTrue(payment.charged_at is not None)
        self.assertEqual(payment.user, item.user)

    def test_refresh(self):
        item = LineItem.objects.create(
            user=User.objects.create(username="test1", email="test1@example.com"),
            amount=5,
            title="Stuff",
        )

        Customer.objects.create(
            user=item.user, customer_id="cus_example", customer_data="{}"
        )

        Customer.objects.update(updated_at=timezone.now() - timedelta(days=60))

        with mock.patch.object(stripe.Charge, "create", return_value={"success": True}):
            with mock.patch.object(
                stripe.Customer, "retrieve", return_value={"marker": True}
            ):
                process_unbound_items(processors=processors)

        customer = Customer.objects.get()
        self.assertEqual(customer.customer, {"marker": True})

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
            side_effect=stripe.error.CardError("problem", "param", "code"),
        ):
            process_unbound_items(processors=processors)

        item = LineItem.objects.get()

        self.assertTrue(item.payment is None)
        self.assertEqual(Payment.objects.count(), 0)

        # Card error mail and nothing else (no please pay mail, processing
        # should have stopped after the card failure)
        self.assertEqual(len(mail.outbox), 1)

    def test_pending_payments(self):
        item = LineItem.objects.create(
            user=User.objects.create(username="test1", email="test1@example.com"),
            amount=5,
            title="Stuff",
        )

        Payment.objects.create_pending(user=item.user)

        process_pending_payments(processors=processors)

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
                side_effect=SomeException(),  # Just not a stripe.error.CardError
            ):
                process_pending_payments(processors=processors)

    def test_custom_processor(self):
        def fail(payment):
            return None  # Invalid return value

        with self.assertRaises(ResultError):
            process_payment(Payment(), processors=[fail])

    def test_result_bool(self):
        with self.assertRaises(ResultError):
            bool(Result.FAILURE)

        with self.assertRaises(ResultError):
            if Result.SUCCESS:
                pass
