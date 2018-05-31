from unittest import mock

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, TestCase
from django.utils.translation import deactivate_all

import stripe
from user_payments.models import Payment
from user_payments.stripe_customers.models import Customer
from user_payments.stripe_customers.moochers import StripeMoocher

from testapp.moochers import moochers


class AttrDict(dict):
    """Dictionary which also allows attribute access to its items"""

    def __getattr__(self, key):
        return self[key]


class Test(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", "admin@test.ch", "blabla")
        self.moocher = moochers["stripe"]
        self.rf = RequestFactory()
        deactivate_all()

    def test_invalid_moocher(self):
        with self.assertRaises(ImproperlyConfigured):
            StripeMoocher(model=Payment, publishable_key=None, secret_key=None)

    def test_moocher_form(self):
        payment = Payment.objects.create(user=self.user, amount=10)
        payment_form = self.moocher.payment_form(self.rf.get("/"), payment)
        self.assertIn(payment.id.hex, payment_form)

    def test_moocher(self):
        payment = Payment.objects.create(user=self.user, amount=10)
        request = self.rf.post("/", {"id": payment.id.hex, "token": "test"})
        request.user = self.user

        with mock.patch.object(
            stripe.Customer, "create", return_value=AttrDict(id="cus_id")
        ):
            with mock.patch.object(stripe.Charge, "create", return_value={}):
                response = self.moocher.charge_view(request)

        self.assertEqual(response.status_code, 302)

        # A customer has been automagically created
        customer = Customer.objects.get()
        self.assertEqual(customer, self.user.stripe_customer)
        self.assertEqual(customer.customer_id, "cus_id")

        payment.refresh_from_db()
        self.assertTrue(payment.charged_at is not None)

    def test_individual_payment(self):
        payment = Payment.objects.create(user=self.user, amount=10)
        request = self.rf.post("/", {"id": payment.id.hex, "token": "test"})
        request.user = AnonymousUser()

        with mock.patch.object(stripe.Charge, "create", return_value={}):
            response = self.moocher.charge_view(request)

        self.assertEqual(response.status_code, 302)

        # No customer, user not logged in... (maybe makes not much sense for
        # user payments .-D
        self.assertEqual(Customer.objects.count(), 0)

        payment.refresh_from_db()
        self.assertTrue(payment.charged_at is not None)

    def test_failing_charge(self):
        payment = Payment.objects.create(user=self.user, amount=10)
        request = self.rf.post("/", {"id": payment.id.hex, "token": "test"})
        request.user = AnonymousUser()

        class Messages(list):
            def add(self, *args):
                self.append(args)

        request._messages = Messages()

        with mock.patch.object(
            stripe.Charge,
            "create",
            side_effect=stripe.CardError("problem", "param", "code"),
        ):
            response = self.moocher.charge_view(request)

        self.assertEqual(response.status_code, 302)

        payment.refresh_from_db()
        self.assertTrue(payment.charged_at is None)
        self.assertEqual(request._messages, [(40, "Card error: problem", "")])
