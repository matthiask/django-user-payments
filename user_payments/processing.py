import logging
from enum import Enum

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.utils.lru_cache import lru_cache
from django.utils.module_loading import import_string

from user_payments.models import LineItem, Payment


logger = logging.getLogger(__name__)


class Result(Enum):
    #: Processor has successfully handled the payment
    SUCCESS = 1
    #: Preconditions of the processor are not met (e.g. no credit card
    #: information). Try next processor.
    SKIP = 2
    #: Abort processing for this payment, do not run other processors
    ABORT = 3


def send_notification_mail(payment):
    # Each time? Each time!
    EmailMessage(
        str(payment),
        "<No body>",
        to=[payment.email],
        bcc=[row[1] for row in settings.MANAGERS],
    ).send(fail_silently=True)
    # No success, but do not abort processing.
    return Result.SKIP


@lru_cache(maxsize=None)
def get_processors(processors=None):
    processors = processors or apps.get_app_config("user_payments").settings.processors
    return [import_string(processor) for processor in processors]


def process_payment(payment, *, processors=None, cancel_on_failure=True):
    logger.info(
        "Processing: %(payment)s by %(email)s",
        {"payment": payment, "email": payment.email},
    )
    success = False

    try:
        for processor in get_processors(processors):
            # Success processing the payment?
            result = processor(payment)
            if result == Result.SUCCESS:
                logger.info(
                    "Success: %(payment)s by %(email)s with %(processor)s",
                    {
                        "payment": payment,
                        "email": payment.email,
                        "processor": processor.__name__,
                    },
                )
                success = True
                break

            elif result == Result.ABORT:
                logger.info(
                    "Warning: Processor %(processor)s aborts processing of"
                    " %(payment)s by %(email)s",
                    {
                        "payment": payment,
                        "email": payment.email,
                        "processor": processor.__name__,
                    },
                )
                break

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


def process_unbound_items(*, processors=None):
    for user in (
        get_user_model()
        .objects.filter(id__in=LineItem.objects.unbound().values("user"))
        .select_related("stripe_customer")
    ):
        payment = Payment.objects.create_pending(user=user)
        if payment:  # pragma: no branch (very unlikely)
            process_payment(payment, processors=processors)


def process_pending_payments(*, processors=None):
    for payment in Payment.objects.pending():
        process_payment(payment, processors=processors, cancel_on_failure=False)
