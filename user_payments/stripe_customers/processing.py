import logging

from django.apps import apps
from django.core.mail import send_mail
from django.utils import timezone

from mooch.signals import post_charge

import stripe

from user_payments.stripe_customers.models import Customer


logger = logging.getLogger(__name__)


def attempt_using_stripe_customers(payment):
    s = apps.get_app_config("user_payments").settings

    try:
        customer = payment.user.stripe_customer
    except Customer.DoesNotExist:
        return False

    if (timezone.now() - customer.updated_at).total_seconds() > 30 * 86400:
        customer.refresh()

    try:
        charge = stripe.Charge.create(
            customer=customer.customer_id,
            amount=payment.amount_cents,
            currency=s.currency,
            description=payment.description,
            idempotency_key="charge-%s-%s" % (payment.id.hex, payment.amount_cents),
        )

    except stripe.CardError as exc:
        logger.exception("Failure charging the customers' card")
        send_mail(str(payment), str(exc), None, [payment.email], fail_silently=True)
        return False

    else:
        payment.payment_service_provider = "stripe"
        payment.charged_at = timezone.now()
        payment.transaction = str(charge)
        payment.save()

        # FIXME sender?
        post_charge.send(
            sender=attempt_using_stripe_customers, payment=payment, request=None
        )

        return True
