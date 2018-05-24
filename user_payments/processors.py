import logging

# from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

import stripe
from mooch.signals import post_charge
from user_payments.models import LineItem, Payment
from user_payments.stripe_customers.models import Customer


logger = logging.getLogger(__name__)


def attempt_using_stripe_customers(payment):
    try:
        customer = payment.user.stripe_customer
    except Customer.DoesNotExist:
        return False

    try:
        charge = stripe.Charge.create(
            customer=customer.customer_id,
            amount=payment.amount_cents,
            currency="CHF",
            description=payment.description,
            idempotency_key=payment.id.hex,
        )

    except stripe.CardError as exc:
        logger.exception("Failure charging the customers' card")
        send_mail(str(payment), str(exc), None, [payment.email], fail_silently=True)
        return False

    else:
        payment.payment_service_provider = "user-payments-stripe-customers"
        payment.charged_at = timezone.now()
        payment.transaction = str(charge)
        payment.save()

        # FIXME sender?
        post_charge.send(
            sender=attempt_using_stripe_customers, payment=payment, request=None
        )

        return True


def send_notification_mail(payment):
    # Each time? Each time!
    send_mail(str(payment), "<No body>", None, [payment.email], fail_silently=True)


default_processors = [attempt_using_stripe_customers, send_notification_mail]


def process_unbound_items(*, processors=default_processors):
    for user in (
        get_user_model()
        .objects.filter(
            id__in=LineItem.objects.unbound().values("user")  # XXX .unpaid()?
        )
        .select_related("stripe_customer")
    ):
        # TODO Also process pending payments? Probably not here.

        payment = Payment.objects.create_pending(user=user)
        if not payment:  # pragma: no cover (unlikely)
            continue

        logger.info(
            "Processing: %(payment)s by %(email)s",
            {"payment": payment, "email": payment.email},
        )

        for processor in processors:
            # Success processing the payment?
            if processor(payment):
                logger.info(
                    "Success: %(payment)s by %(email)s with %(processor)s",
                    {
                        "payment": payment,
                        "email": payment.email,
                        "processor": processor.__name__,
                    },
                )
                break
        else:

            logger.warning(
                "Canceling: %(payment)s by %(email)s",
                {"payment": payment, "email": payment.email},
            )
            payment.cancel_pending()
