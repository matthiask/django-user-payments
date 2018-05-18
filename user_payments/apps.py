from datetime import timedelta
from types import SimpleNamespace

from django.apps import AppConfig
from django.utils.functional import cached_property
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _


class UserPayments(AppConfig):
    name = "user_payments"
    verbose_name = capfirst(_("user payments"))

    default_settings = {"currency": "CHF", "grace_period": timedelta(days=3)}

    @cached_property
    def settings(self):
        from django.conf import settings

        return SimpleNamespace(
            **{**self.default_settings, **getattr(settings, "USER_PAYMENTS", {})}
        )
