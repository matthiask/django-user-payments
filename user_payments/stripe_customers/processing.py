import logging

from django.apps import apps
from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from mooch.signals import post_charge

import stripe

from user_payments.processing import Result
from user_payments.stripe_customers.models import Customer


logger = logging.getLogger(__name__)


def with_stripe_customer(payment):
    s = apps.get_app_config("user_payments").settings

    try:
        customer = payment.user.stripe_customer
    except Customer.DoesNotExist:
        return Result.FAILURE

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
        EmailMessage(
            str(payment),
            str(exc),
            to=[payment.email],
            bcc=[row[1] for row in settings.MANAGERS],
        ).send(fail_silently=True)
        return Result.ABORT

    else:
        payment.payment_service_provider = "stripe"
        payment.charged_at = timezone.now()
        payment.transaction = str(charge)
        payment.save()

        # FIXME sender?
        post_charge.send(sender=with_stripe_customer, payment=payment, request=None)
        return Result.SUCCESS
