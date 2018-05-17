from django.apps import AppConfig
from django.conf import settings
from django.utils.text import capfirst
from django.utils.translation import ugettext_lazy as _

import stripe


class StripeCustomersConfig(AppConfig):
    name = "user.payments.stripe_customers"
    verbose_name = capfirst(_("stripe customers"))

    def ready(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY
