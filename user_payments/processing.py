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


def process_payment(payment, *, processors=default_processors, cancel_on_failure=True):
    logger.info(
        "Processing: %(payment)s by %(email)s",
        {"payment": payment, "email": payment.email},
    )
    success = False

    try:
        for processor in processors:
            # Success processing the payment?
            success = processor(payment)
            if success:
                logger.info(
                    "Success: %(payment)s by %(email)s with %(processor)s",
                    {
                        "payment": payment,
                        "email": payment.email,
                        "processor": processor.__name__,
                    },
                )
                return True
        else:
            logger.warning(
                "Warning: No success processing %(payment)s by %(email)s",
                {"payment": payment, "email": payment.email},
            )

    except Exception:
        logger.exception("Exception while processing %(payment)s by %(email)s")
        success = False
        raise

    finally:
        if not success and cancel_on_failure:
            payment.cancel_pending()


def process_unbound_items(*, processors=default_processors):
    for user in (
        get_user_model()
        .objects.filter(id__in=LineItem.objects.unbound().values("user"))
        .select_related("stripe_customer")
    ):
        payment = Payment.objects.create_pending(user=user)
        if payment:  # pragma: no branch (very unlikely)
            process_payment(payment, processors=processors)


def process_pending_payments(*, processors=default_processors):
    for payment in Payment.objects.pending():
        process_payment(payment, processors=processors, cancel_on_failure=False)
