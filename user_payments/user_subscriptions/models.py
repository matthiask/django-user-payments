from datetime import date, datetime, time, timedelta

from django.apps import apps
from django.conf import settings
from django.db import models, transaction
from django.db.models import Max, signals
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from user_payments.models import LineItem, Payment

from .utils import recurring


class SubscriptionQuerySet(models.QuerySet):
    def for_code(self, code):
        try:
            return self.get(code=code)
        except self.model.DoesNotExist:
            return None


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
        with transaction.atomic():
            changed = False

            try:
                subscription = self.get(user=user, code=code)
            except Subscription.DoesNotExist:
                subscription = self.create(user=user, code=code, **kwargs)
            else:
                for key, value in kwargs.items():
                    if getattr(subscription, key) != value:
                        changed = True
                        setattr(subscription, key, value)

                subscription.save()

                if not changed:
                    return subscription

            subscription.delete_pending_periods()

            if subscription.paid_until > date.today():
                # paid_until might already have been changed in the save()
                # call above. So look at paid_untli and not at starts_on
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
        for subscription in self.filter(
            renew_automatically=True,
            paid_until__lt=timezone.now() - s.disable_autorenewal_after,
        ):
            subscription.cancel()


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

    objects = SubscriptionManager.from_queryset(SubscriptionQuerySet)()

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
        self.paid_until = self.periods.paid().aggregate(m=Max("ends_on"))["m"]
        if save:
            self.save()

    update_paid_until.alters_data = True

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
    def grace_period_ends_at(self):
        s = apps.get_app_config("user_payments").settings
        return self.paid_until_at + s.grace_period

    @property
    def is_active(self):
        s = apps.get_app_config("user_payments").settings
        return timezone.now() <= self.paid_until_at + s.grace_period

    @property
    def in_grace_period(self):
        return self.paid_until_at <= timezone.now() <= self.grace_period_ends_at

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

        latest_ends_on = self.periods.aggregate(m=Max("ends_on"))["m"]
        periods = []

        if this_start <= end:
            while True:
                next_start = next(days)
                if latest_ends_on is None or this_start > latest_ends_on:
                    periods.append(
                        self.periods.create(
                            starts_on=this_start, ends_on=next_start - timedelta(days=1)
                        )
                    )
                this_start = next_start

                if this_start > end:
                    break

        return periods

    create_periods.alters_data = True

    def delete_pending_periods(self):
        for period in self.periods.select_related("line_item__payment"):
            line_item = period.line_item
            if line_item:
                if line_item.payment:
                    if line_item.payment.charged_at:
                        continue
                    line_item.payment.cancel_pending()
            period.delete()
            if line_item:
                line_item.delete()

    delete_pending_periods.alters_data = True

    def cancel(self):
        self.ends_on = self.paid_until
        self.renew_automatically = False
        self.save()

        self.delete_pending_periods()

    cancel.alters_data = True


def payment_changed(sender, instance, **kwargs):
    affected = SubscriptionPeriod.objects.filter(line_item__payment=instance.pk).values(
        "subscription"
    )
    for subscription in Subscription.objects.filter(pk__in=affected):
        subscription.update_paid_until()


signals.post_save.connect(payment_changed, sender=Payment)
signals.post_delete.connect(payment_changed, sender=Payment)


class SubscriptionPeriodManager(models.Manager):
    def paid(self):
        """
        Return subscription periods that have been paid for.
        """
        return self.filter(line_item__payment__charged_at__isnull=False)

    def create_line_items(self, *, until=None):
        for period in self.filter(
            line_item__isnull=True, starts_on__lte=until or date.today()
        ):
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
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("line item"),
    )

    objects = SubscriptionPeriodManager()

    class Meta:
        get_latest_by = "starts_on"
        unique_together = (("subscription", "starts_on"),)
        verbose_name = _("subscription period")
        verbose_name_plural = _("subscription periods")

    def __str__(self):
        return "%s (%s - %s)" % (self.subscription, self.starts_on, self.ends_on)

    def create_line_item(self):
        """
        Create a user payments line item for this subscription period.
        """
        if not self.line_item:
            self.line_item = LineItem.objects.create(
                user=self.subscription.user,
                title=str(self),
                amount=self.subscription.amount,
            )
            self.save()

    create_line_item.alters_data = True

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
