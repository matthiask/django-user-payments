import json
import os
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils.translation import deactivate_all

import stripe
from user_payments.stripe_customers.models import Customer


class Test(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser("admin", "admin@test.ch", "blabla")
        deactivate_all()

    def login(self):
        client = Client()
        client.force_login(self.user)
        return client

    def test_model(self):
        with open(
            os.path.join(settings.BASE_DIR, "customer.json"), encoding="utf-8"
        ) as f:
            data = json.load(f)

        with mock.patch.object(stripe.Customer, "retrieve", return_value=data):
            customer = Customer.objects.create(
                customer_id="cus_BVuJJZtpmo1234", user=self.user
            )

        self.assertEqual(str(customer), "cus_BVuJJZ********")
        self.assertEqual(customer.active_subscriptions, {})

        client = self.login()

        response = client.get(
            "/admin/stripe_customers/customer/%s/change/" % customer.pk
        )
        self.assertContains(
            response, "&quot;id&quot;: &quot;card_1B8sUM******************&quot;"
        )
        self.assertNotContains(response, "cus_BVuJJZtpmo1234")

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

        # No change detection!
        customer.save()
        customer = Customer.objects.get()
        self.assertEqual(customer.customer_data, '{"bla": 3}')
        self.assertEqual(customer.customer, {"bla": 3})

    def test_refresh(self):
        with mock.patch.object(stripe.Customer, "retrieve", return_value={"bla": 3}):
            Customer(customer_id="cus_1234567890", user=self.user).refresh()

        customer = Customer.objects.get()
        self.assertEqual(customer.customer_data, '{"bla": 3}')
        self.assertEqual(customer.customer, {"bla": 3})

    def test_nocrash(self):
        customer = Customer()
        self.assertEqual(customer.active_subscriptions, {})
