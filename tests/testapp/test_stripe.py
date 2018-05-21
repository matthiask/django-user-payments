from unittest import mock
import stripe

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils.translation import deactivate_all

from user_payments.stripe_customers.models import Customer


class Test(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser("admin", "admin@test.ch", "blabla")
        deactivate_all()

    def test_model(self):

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
            Customer(
                customer_id="cus_1234567890", user=self.user
            ).refresh()

        customer = Customer.objects.get()
        self.assertEqual(customer.customer_data, '{"bla": 3}')
        self.assertEqual(customer.customer, {"bla": 3})
