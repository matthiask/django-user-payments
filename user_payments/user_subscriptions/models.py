from datetime import date, datetime, time, timedelta

from django.apps import apps
from django.conf import settings
from django.db import models
from django.db.models import Max
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from user_payments.models import LineItem

from .utils import recurring


class SubscriptionManager(models.Manager):
    def create(self, *, user, code, periodicity, amount, **kwargs):
        """
        Make it a ``TypeError`` to forget fields.
        """
        return super().create(
            user=user, code=code, periodicity=periodicity, amount=amount, **kwargs
        )

    def ensure(self, *, user, code, **kwargs):
        """
        Ensure that the user is subscribed to the subscription specified by
        ``code``. Pass additional fields for the subscription as kwargs.

        If the subscription is still in a paid period this also ensures that
        new subscription periods aren't created too early.
        """
        subscription, created = self.update_or_create(
            user=user, code=code, defaults=kwargs
        )
        if not created:
            subscription.delete_pending_periods()
        if subscription.paid_until > date.today():
            subscription.starts_on = subscription.paid_until + timedelta(days=1)
            subscription.save()
        return subscription

    def create_periods(self):
        for subscription in self.filter(renew_automatically=True):
            subscription.create_periods()

    def disable_autorenewal(self):
        """
        Disable autorenewal for subscriptions that are past due

        Uses the ``USER_PAYMENTS['disable_autorenewal_after']`` timedelta to
        determine the timespan after which autorenewal is disabled for unpaid
        subscriptions. Defaults to 15 days.
        """
        s = apps.get_app_config("user_payments").settings
        self.filter(
            renew_automatically=True,
            paid_until__lt=timezone.now() - s.disable_autorenewal_after,
        ).update(renew_automatically=False)


class Subscription(models.Model):
    """
    How to quickly generate a new subscription and fetch the first payment::

        user = request.user  # Fetch the user from somewhere

        subscription, created = Subscription.objects.get_or_create(
            user=user,
            code='plan',  # Or whatever makes sense for you
            defaults={
                'title': 'You should want to provide this',
                'periodicity': 'yearly',  # or monthly, or weekly. NOT manually.
                'amount': 60,
            },
        )
        for period in subscription.create_periods():
            period.create_line_item()
        first_payment = Payment.objects.create_pending(user=user)
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="user_subscriptions",
        verbose_name=_("user"),
    )
    code = models.CharField(
        _("code"),
        max_length=20,
        help_text=_(
            "Codes must be unique per user. Allows identifying the subscription."
        ),
    )
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    title = models.CharField(_("title"), max_length=200)
    starts_on = models.DateField(_("starts on"))
    ends_on = models.DateField(_("ends on"), blank=True, null=True)
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

    renew_automatically = models.BooleanField(_("renew automatically"), default=True)
    paid_until = models.DateField(_("paid until"), blank=True)

    objects = SubscriptionManager()

    class Meta:
        unique_together = (("user", "code"),)
        verbose_name = _("subscription")
        verbose_name_plural = _("subscriptions")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.starts_on:
            self.starts_on = date.today()
        if not self.paid_until or self.paid_until < self.starts_on:
            # New subscription instance or restarted subscription with
            # inactivity period.
            self.paid_until = self.starts_on - timedelta(days=1)
        super().save(*args, **kwargs)

        # Update unbound line items with new amount.
        LineItem.objects.unbound().filter(subscriptionperiod__subscription=self).update(
            amount=self.amount
        )

    save.alters_data = True

    def update_paid_until(self, save=True):
        # TODO call this from somewhere...
        self.paid_until = (
            self.periods.paid().aggregate(m=Max("ends_on"))["m"] or self.paid_until
        )
        if save:
            self.save()

    @property
    def starts_at(self):
        return timezone.make_aware(
            datetime.combine(self.starts_on, time.min), timezone.get_default_timezone()
        )

    @property
    def ends_at(self):
        return (
            timezone.make_aware(
                datetime.combine(self.ends_on, time.max),
                timezone.get_default_timezone(),
            )
            if self.ends_on
            else None
        )

    @property
    def paid_until_at(self):
        return timezone.make_aware(
            datetime.combine(self.paid_until, time.max), timezone.get_default_timezone()
        )

    @property
    def is_active(self):
        s = apps.get_app_config("user_payments").settings
        return timezone.now() <= self.paid_until_at + s.grace_period

    @property
    def in_grace_period(self):
        s = apps.get_app_config("user_payments").settings
        return (
            self.paid_until_at <= timezone.now() <= self.paid_until_at + s.grace_period
        )

    def create_periods(self, *, until=None):
        """
        Create period instances for this subscription, up to either today or
        the end of the subscription, whichever date is earlier.

        ``until`` is interpreted as "up to and including".
        """
        end = until or date.today()
        if self.ends_on:
            end = min(self.ends_on, end)
        days = recurring(self.starts_on, self.periodicity)
        this_start = next(days)

        periods = list(self.periods.all())

        if this_start <= end:
            existing = set(p.starts_on for p in periods)
            while True:
                next_start = next(days)
                if this_start not in existing:
                    p, _created = self.periods.get_or_create(
                        starts_on=this_start, ends_on=next_start - timedelta(days=1)
                    )
                    periods.append(p)
                this_start = next_start

                # TODO This might be a good place to already generate periods
                # for the near future to inform users that a payment will soon
                # be due.

                if this_start > end:
                    break

        return periods

    create_periods.alters_data = True

    def delete_pending_periods(self):
        for period in self.periods.select_related("line_item__payment"):
            if period.line_item:
                if period.line_item.payment:
                    if period.line_item.payment.charged_at:
                        continue
                    period.line_item.payment.cancel_pending()
                period.line_item.delete()
            period.delete()

    delete_pending_periods.alters_data = True


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
    starts_on = models.DateField(_("starts on"))
    ends_on = models.DateField(_("ends on"))
    line_item = models.OneToOneField(
        LineItem,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("line item"),
    )

    objects = SubscriptionPeriodManager()

    class Meta:
        unique_together = (("subscription", "starts_on"),)
        verbose_name = _("subscription period")
        verbose_name_plural = _("subscription periods")

    def __str__(self):
        return "%s (%s - %s)" % (self.subscription, self.starts_on, self.ends_on)

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
