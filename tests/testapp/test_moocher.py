from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import RequestFactory, TestCase
from django.utils.translation import deactivate_all

import stripe
from user_payments.models import LineItem, Payment
from user_payments.processing import process_unbound_items
from user_payments.stripe_customers.models import Customer
from user_payments.stripe_customers.moochers import StripeMoocher


class AttrDict(dict):
    def __getattr__(self, key):
        return self[key]


class Test(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser("admin", "admin@test.ch", "blabla")
        deactivate_all()

    def login(self):
        client = Client()
        client.force_login(self.user)
        return client

    def test_moocher(self):
        moocher = StripeMoocher(model=Payment, publishable_key="pk", secret_key="sk")

        rf = RequestFactory()

        payment = Payment.objects.create(user=self.user, amount=10)
        request = rf.post('/', {"id": payment.id.hex, "token": "test"})
        request.user = self.user

        with mock.patch.object(stripe.Customer, "create", return_value=AttrDict(id="cus_id")):
            with mock.patch.object(stripe.Charge, "create", return_value={}):
                response = moocher.charge_view(request)

        self.assertEqual(self.user.stripe_customer.customer_id, "cus_id")

        payment.refresh_from_db()
        self.assertTrue(payment.charged_at is not None)

        print(response)
