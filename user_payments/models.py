from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy as _

from mooch.models import Payment as AbstractPayment


class PaymentManager(models.Manager):

    def create_pending(self, *, user):
        """
        Create an unpaid payment instance with all line items for the given
        user that have not been bound to a payment instance yet.

        Returns ``None`` if there are no unbound line items for the given user.
        """
        # XXX payment__isnull | payment__charged_at__isnull?
        with transaction.atomic():
            pending = LineItem.objects.filter(user=user, payment__isnull=True)
            if not len(pending):
                return None

            payment = self.create(
                user=user, amount=sum((item.amount for item in pending), 0)
            )
            pending.update(payment=payment)
            return payment


class Payment(AbstractPayment):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="user_payments",
        verbose_name=_("user"),
    )

    objects = PaymentManager()

    def __str__(self):
        if self.charged_at:
            return gettext("Payment of %s") % self.amount
        return gettext("Pending payment of %s") % self.amount

    def save(self, *args, **kwargs):
        if not self.email:
            self.email = self.user.email
        super().save(*args, **kwargs)

    save.alters_data = True


class LineItem(models.Model):
    """
    Individual line items may be created directly using the manager method. A
    minimal example follows::

        @login_required
        def some_view(request):
            # This request costs 5 cents!
            LineItem.objects.create(
                user=request.user,
                amount=Decimal('0.05'),
                title='Request to some_view',
            )
            # Rest of view

    If you already have a payment instance at hand you may pass it as well.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="user_lineitems",
        verbose_name=_("user"),
    )
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    title = models.CharField(_("title"), max_length=200)
    amount = models.DecimalField(_("amount"), max_digits=10, decimal_places=2)

    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="lineitems",
        verbose_name=_("payment"),
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("line item")
        verbose_name_plural = _("line items")

    def __str__(self):
        return self.title
