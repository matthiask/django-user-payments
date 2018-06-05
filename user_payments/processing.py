import logging
from enum import Enum

from django.contrib.auth import get_user_model

from user_payments.models import LineItem, Payment


logger = logging.getLogger(__name__)


class Result(Enum):
    #: Processor has successfully handled the payment
    SUCCESS = 1
    #: Preconditions of the processor are not met (e.g. no credit card
    #: information). Try next processor.
    FAILURE = 2
    #: Terminates processing for this payment, do not run other processors
    TERMINATE = 3

    def __bool__(self):
        raise ResultError("Results may not be interpreted as bools")


class ResultError(Exception):
    pass


def process_payment(payment, *, processors, cancel_on_failure=True):
    logger.info(
        "Processing: %(payment)s by %(email)s",
        {"payment": payment, "email": payment.email},
    )
    success = False

    try:
        for processor in processors:
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
                return True

            elif result == Result.TERMINATE:
                logger.info(
                    "Warning: Processor %(processor)s terminates processing of"
                    " %(payment)s by %(email)s",
                    {
                        "payment": payment,
                        "email": payment.email,
                        "processor": processor.__name__,
                    },
                )
                break

            elif result == Result.FAILURE:
                # It's fine, do nothing.
                pass

            else:
                raise ResultError(
                    "Invalid result %r from %s" % (result, processor.__name__)
                )

        else:
            logger.warning(
                "Warning: No success processing %(payment)s by %(email)s",
                {"payment": payment, "email": payment.email},
            )

    except Exception:
        logger.exception("Exception while processing %(payment)s by %(email)s")
        raise

    finally:
        if not success and cancel_on_failure:
            payment.cancel_pending()


def process_unbound_items(*, processors):
    for user in (
        get_user_model()
        .objects.filter(id__in=LineItem.objects.unbound().values("user"))
        .select_related("stripe_customer")
    ):
        payment = Payment.objects.create_pending(user=user)
        if payment:  # pragma: no branch (very unlikely)
            process_payment(payment, processors=processors)


def process_pending_payments(*, processors):
    for payment in Payment.objects.pending():
        process_payment(payment, cancel_on_failure=False, processors=processors)
