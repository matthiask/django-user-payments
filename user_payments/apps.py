from datetime import timedelta
from types import SimpleNamespace

from django.apps import AppConfig
from django.utils.module_loading import import_string
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _


class UserPayments(AppConfig):
    name = "user_payments"
    verbose_name = capfirst(_("user payments"))
    default_settings = {
        "currency": "CHF",
        "grace_period": timedelta(days=7),
        "disable_autorenewal_after": timedelta(days=15),
        "processors": [
            # "user_payments.stripe_customers.processing.with_stripe_customer",
            "user_payments.processing.please_pay_mail"
        ],
    }

    def ready(self):
        from django.conf import settings

        self.settings = SimpleNamespace(
            **{**self.default_settings, **getattr(settings, "USER_PAYMENTS", {})}
        )
        self.processors = [import_string(proc) for proc in self.settings.processors]
