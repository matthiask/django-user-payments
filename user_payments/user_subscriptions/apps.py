from django.apps import AppConfig
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _


class UserSubscriptions(AppConfig):
    name = "user_payments.user_subscriptions"
    verbose_name = capfirst(_("user subscriptions"))
