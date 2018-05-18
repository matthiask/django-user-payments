import logging

from django.utils import timezone

import stripe
from user_payments.models import LineItem, Payment
from user_payments.stripe_customers.models import Customer


logger = logging.getLogger(__name__)


class StripeSubscriptionsProcessor:

    def process(self):
        for customer in Customer.objects.filter(
            user__in=LineItem.objects.unbound().values("user")  # XXX .unpaid()?
        ).select_related(
            "user"
        ):
            payment = Payment.objects.create_pending(user=customer.user)
            if not payment:
                continue

            try:
                # Really do this right away?
                charge = stripe.Charge.create(
                    customer=customer.customer_id,
                    amount=payment.instance.amount_cents,
                    currency="CHF",
                    idempotency_key=payment.id.hex,
                )
            except stripe.CardError as exc:
                # TODO do a thing...
                logger.exception(exc)

                # TODO Probably should also send a mail?
                payment.lineitems.update(payment=None)
                payment.delete()

            else:
                # TODO check for more errors?
                payment.charged_at = timezone.now()
                payment.transaction = str(charge)
                payment.save()

            # FIXME sender? request?
            # post_charge.sender(sender=self, payment=instance, request=None)
