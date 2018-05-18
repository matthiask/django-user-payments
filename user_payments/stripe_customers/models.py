from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

import stripe


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
    customer = JSONField(_("customer"), blank=True, null=True)

    class Meta:
        verbose_name = _("customer")
        verbose_name_plural = _("customers")

    def __str__(self):
        return "%s%s" % (self.customer_id[:10], "*" * (len(self.customer_id) - 10))

    def save(self, *args, **kwargs):
        if not self.pk:
            self.refresh(save=False)
        super().save(*args, **kwargs)

    save.alters_data = True

    def refresh(self, save=True):
        self.customer = stripe.Customer.retrieve(
            self.customer_id, expand=["default_source"]
        )
        if save:
            self.save()

    @cached_property
    def active_subscriptions(self):
        if not self.customer:
            return {}
        return {
            subscription["plan"]["id"]: True
            for subscription in self.customer["subscriptions"]["data"]
            if subscription["status"] in {"trialing", "active", "past due"}
        }
