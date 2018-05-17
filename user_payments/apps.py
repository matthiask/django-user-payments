from django.apps import AppConfig
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _


class UserPayments(AppConfig):
    name = "user_payments"
    verbose_name = capfirst(_("user payments"))
