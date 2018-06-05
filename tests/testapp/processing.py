import json
import logging

from django.apps import apps
from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import ObjectDoesNotExist
from django.utils import timezone

import stripe
from mooch.signals import post_charge

from user_payments.processing import Result


logger = logging.getLogger(__name__)


def please_pay_mail(payment):
    # Each time? Each time!
    EmailMessage(
        str(payment),
        "<No body>",
        to=[payment.email],
        bcc=[row[1] for row in settings.MANAGERS],
    ).send(fail_silently=True)
    # No success, but do not terminate processing.
    return Result.FAILURE


def with_stripe_customer(payment):
    try:
        customer = payment.user.stripe_customer
    except ObjectDoesNotExist:
        return Result.FAILURE

    if (timezone.now() - customer.updated_at).total_seconds() > 30 * 86400:
        customer.refresh()

    s = apps.get_app_config("user_payments").settings

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
        return Result.TERMINATE

    else:
        payment.payment_service_provider = "stripe"
        payment.charged_at = timezone.now()
        payment.transaction = json.dumps(charge)
        payment.save()

        # FIXME sender?
        post_charge.send(sender=with_stripe_customer, payment=payment, request=None)
        return Result.SUCCESS


processors = [with_stripe_customer, please_pay_mail]
