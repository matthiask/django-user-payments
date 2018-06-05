from types import SimpleNamespace

from django.apps import AppConfig
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _

import stripe


class StripeCustomersConfig(AppConfig):
    name = "user_payments.stripe_customers"
    verbose_name = capfirst(_("stripe customers"))

    def ready(self):
        from django.conf import settings

        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.settings = SimpleNamespace(
            publishable_key=settings.STRIPE_PUBLISHABLE_KEY,
            secret_key=settings.STRIPE_SECRET_KEY,
        )
