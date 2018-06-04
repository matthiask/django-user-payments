import json

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

import stripe


class CustomerManager(models.Manager):
    def with_token(self, *, user, token):
        """
        Add or replace a credit card for a given user
        """

        try:
            customer_id = user.stripe_customer.customer_id
        except Customer.DoesNotExist:
            obj = stripe.Customer.create(
                email=user.email, source=token, expand=["default_source"]
            )
            customer = self.model(user=user, customer_id=obj.id)
            customer.customer = obj
            customer.save()
            return customer

        else:
            obj = stripe.Customer.retrieve(customer_id)
            obj.source = token
            obj.save()
            user.stripe_customer.refresh()
            return user.stripe_customer


class Customer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("user"),
        related_name="stripe_customer",
    )
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    customer_id = models.CharField(_("customer ID"), max_length=50, unique=True)
    customer_data = models.TextField(_("customer data"), blank=True)

    objects = CustomerManager()

    class Meta:
        verbose_name = _("customer")
        verbose_name_plural = _("customers")

    def __str__(self):
        return "%s%s" % (self.customer_id[:10], "*" * (len(self.customer_id) - 10))

    def save(self, *args, **kwargs):
        if hasattr(self, "_customer_data_cache"):
            self.customer_data = json.dumps(self._customer_data_cache)
        if not self.customer_data:
            self.refresh(save=False)
        super().save(*args, **kwargs)

    save.alters_data = True

    @property
    def customer(self):
        """
        Return the parsed version of the JSON blob or ``None`` if there is no
        data around to be parsed.

        After calling ``Customer.refresh()`` this property even returns the
        objects returned by the Stripe library as they come.

        Does NOT work with ``instance.refresh_from_db()`` -- you have to fetch
        a completely new object from the database.
        """
        if not hasattr(self, "_customer_data_cache"):
            self._customer_data_cache = json.loads(self.customer_data or "{}")
        return self._customer_data_cache

    @customer.setter
    def customer(self, value):
        self._customer_data_cache = value
        self.customer_data = json.dumps(self._customer_data_cache)

    def refresh(self, save=True):
        self.customer = stripe.Customer.retrieve(
            self.customer_id, expand=["default_source"]
        )
        if save:
            self.save()
