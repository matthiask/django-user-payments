import json
import os
from unittest import mock

import stripe
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils.translation import deactivate_all

from user_payments.stripe_customers.models import Customer


class AttrDict(dict):
    """Dictionary which also allows attribute access to its items"""

    def __getattr__(self, key):
        return self[key]

    def save(self):
        # stripe.Customer.save()
        pass


class Test(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", "admin@test.ch", "blabla")
        deactivate_all()

    @property
    def data(self):
        with open(
            os.path.join(settings.BASE_DIR, "customer.json"), encoding="utf-8"
        ) as f:
            return AttrDict(json.load(f))

    def login(self):
        client = Client()
        client.force_login(self.user)
        return client

    def test_model(self):
        with mock.patch.object(stripe.Customer, "retrieve", return_value=self.data):
            customer = Customer.objects.create(
                customer_id="cus_BdO5X6Bj123456", user=self.user
            )

        self.assertEqual(str(customer), "cus_BdO5X6********")

        client = self.login()

        response = client.get(
            "/admin/stripe_customers/customer/%s/change/" % customer.pk
        )
        self.assertContains(
            response, "&quot;id&quot;: &quot;card_1BG7Jj******************&quot;"
        )
        self.assertNotContains(response, "cus_BdO5X6Bj123456")

    def test_property(self):

        with mock.patch.object(stripe.Customer, "retrieve", return_value={"bla": 3}):
            customer = Customer.objects.create(
                customer_id="cus_1234567890", user=self.user
            )

        self.assertEqual(customer.customer_data, '{"bla": 3}')
        self.assertEqual(str(customer), "cus_123456****")

        customer = Customer.objects.get()
        self.assertEqual(customer.customer_data, '{"bla": 3}')
        self.assertEqual(customer.customer, {"bla": 3})

        cache = customer.customer
        cache["test"] = 5

        self.assertEqual(customer.customer_data, '{"bla": 3}')
        self.assertEqual(customer.customer, {"bla": 3, "test": 5})

        # Change is serialized when calling .save()
        customer.save()
        customer = Customer.objects.get()
        self.assertEqual(customer.customer, {"bla": 3, "test": 5})

    def test_refresh(self):
        with mock.patch.object(stripe.Customer, "retrieve", return_value={"bla": 3}):
            Customer(customer_id="cus_1234567890", user=self.user).refresh()

        customer = Customer.objects.get()
        self.assertEqual(customer.customer_data, '{"bla": 3}')
        self.assertEqual(customer.customer, {"bla": 3})

    def test_with_token_create(self):
        with mock.patch.object(stripe.Customer, "create", return_value=self.data):
            customer = Customer.objects.with_token(user=self.user, token="bla")
        self.assertEqual(customer.customer_id, "cus_BdO5X6Bj123456")

    def test_with_token_update(self):
        with mock.patch.object(stripe.Customer, "retrieve", return_value=self.data):
            c1 = Customer.objects.create(
                user=self.user, customer_id="cus_BdO5X6Bj123456"
            )
            customer = Customer.objects.with_token(user=self.user, token="bla")
        self.assertEqual(customer.customer_id, "cus_BdO5X6Bj123456")
        self.assertEqual(c1.pk, customer.pk)
