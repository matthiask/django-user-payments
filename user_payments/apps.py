from datetime import timedelta
from types import SimpleNamespace

from django.apps import AppConfig
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _


class UserPayments(AppConfig):
    name = "user_payments"
    verbose_name = capfirst(_("user payments"))
    default_settings = {
        "currency": "CHF",
        "grace_period": timedelta(days=7),
        "disable_autorenewal_after": timedelta(days=15),
    }

    def ready(self):
        from django.conf import settings

        self.settings = SimpleNamespace(
            **{**self.default_settings, **getattr(settings, "USER_PAYMENTS", {})}
        )
