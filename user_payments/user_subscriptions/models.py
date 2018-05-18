from datetime import date, timedelta

from django.conf import settings
from django.db import models
from django.db.models import Max
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from user_payments.models import LineItem

from .utils import recurring


class SubscriptionManager(models.Manager):

    def create_periods(self):
        for subscription in self.all():
            subscription.create_periods()


class Subscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="user_subscriptions",
        verbose_name=_("user"),
    )
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    title = models.CharField(_("title"), max_length=200)
    starts_at = models.DateTimeField(_("starts at"))
    ends_at = models.DateTimeField(_("ends at"), blank=True, null=True)
    periodicity = models.CharField(
        _("periodicity"),
        max_length=20,
        choices=[
            ("yearly", _("yearly")),
            ("monthly", _("monthly")),
            ("weekly", _("weekly")),
            ("manually", _("manually")),
        ],
    )
    amount = models.DecimalField(_("amount"), max_digits=10, decimal_places=2)

    renew_automatically = models.BooleanField(_("renew automatically"))
    paid_until = models.DateTimeField(_("paid until"), blank=True)

    objects = SubscriptionManager()

    class Meta:
        verbose_name = _("subscription")
        verbose_name_plural = _("subscriptions")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.paid_until:
            self.paid_until = self.starts_at or timezone.now()
        super().save(*args, **kwargs)

    save.alters_data = True

    def update_paid_until(self, save=True):
        self.paid_until = self.periods.paid().aggregate(m=Max("ends_at"))[
            "m"
        ] or self.paid_until
        if save:
            self.save()

    @property
    def is_active(self):
        # TODO grace period?
        return self.starts_at <= timezone.now() <= self.paid_until

    def create_periods(self, *, until=None):
        """
        Create period instances for this subscription, up to either today or
        the end of the subscription, whichever date is earlier.
        """
        end = until or date.today()
        if self.ends_at:
            end = min(self.ends_at, end)
        days = recurring(self.starts_at, self.periodicity)
        this_start = next(days)

        periods = list(self.periods.all())

        existing = set(p.starts_at for p in periods)
        while True:
            next_start = next(days)
            if this_start not in existing:
                p, _created = self.periods.get_or_create(
                    starts_at=this_start, ends_at=next_start - timedelta(days=1)
                )
                periods.append(p)
            this_start = next_start

            # TODO This might be a good place to already generate periods
            # for the near future to inform users that a payment will soon
            # be due.

            if this_start >= end:
                break

        return periods

    create_periods.alters_data = True


class SubscriptionPeriodManager(models.Manager):

    def paid(self):
        """
        Return subscription periods that have been paid for.
        """
        return self.filter(line_item__payment__charged_at__isnull=False)

    def create_line_items(self):
        # Not really a good QuerySet method, should be a manager method, but
        # whatever...
        for period in self.filter(line_item__isnull=True):
            period.create_line_item()


class SubscriptionPeriod(models.Model):
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="periods",
        verbose_name=_("subscription"),
    )
    starts_at = models.DateField(_("starts at"))
    ends_at = models.DateField(_("ends at"))
    line_item = models.OneToOneField(
        LineItem,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("line item"),
    )

    objects = SubscriptionPeriodManager()

    class Meta:
        unique_together = (("subscription", "starts_at"),)
        verbose_name = _("subscription period")
        verbose_name_plural = _("subscription periods")

    def __str__(self):
        return "%s (%s - %s)" % (self.subscription, self.starts_at, self.ends_at)

    def create_line_item(self):
        """
        Create a user payments line item for this subscription period.
        """
        # TODO Maybe create periods and line items early,
        # e.g. 7 days before new period begins?
        self.line_item = LineItem.objects.create(
            user=self.subscription.user,
            title=str(self),
            amount=self.subscription.amount,
        )
        self.save()

    create_line_item.alters_data = True
