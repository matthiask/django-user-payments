import logging

from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from user_payments.models import LineItem, Payment


logger = logging.getLogger(__name__)


class Processors:

    def __init__(self):
        self._processors = []

    def add(self, processor, *, priority=0):
        self._processors.append((-priority, processor))
        self._processors.sort()

    def __iter__(self):
        return (item[1] for item in self._processors)


default_processors = Processors()


def send_notification_mail(payment):
    # Each time? Each time!
    send_mail(str(payment), "<No body>", None, [payment.email], fail_silently=True)


default_processors.add(send_notification_mail, priority=-1)


def process_payment(payment, *, processors=default_processors):
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
        if payment:  # pragma: no branch (very unlikely)
            process_payment(payment, processors=processors)
