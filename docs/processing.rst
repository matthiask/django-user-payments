Processing
==========

django-user-payments comes with a framework for processing payments
outside moochers.

The general structure of an individual processor is as follows:

.. code-block:: python

    from user_payments.processing import Result

    def psp_process(payment):
        # Check prerequisites
        if not <prerequisites>:
            return Result.FAILURE

        # Try settling the payment
        if <success>:
            return Result.SUCCESS

        return Result.FAILURE

The processor **must** return a  ``Result`` enum value. Individual
processor results **must** not be evaluated in a boolean context.

The following ``Result`` values exist:

- ``Result.SUCCESS``: Payment was successfully charged for.
- ``Result.FAILURE``: This processor failed, try the next.
- ``Result.TERMINATE``: Terminate processing for this payment, do not
  run any further processors.

When using ``process_payment()`` as you should (see below) and an
individual processor raises exceptions the exception is logged, the
payment is canceled if ``cancel_on_failure`` is ``True`` (the default)
and the exception is reraised. In other words: Processors should **not**
raise exceptions.


Writing your processors
~~~~~~~~~~~~~~~~~~~~~~~

django-user-payments does not bundle any processors, but makes it
relatively straightforward to write your own.


The Stripe customers processor
------------------------------

This processors' prerequisites are a Stripe customer instance. If the
prerequisites are fulfilled, this processor tries charging the user, and
if this fails, sends an error mail to the user and terminates further
processing:

.. code-block:: python

    import json
    import logging

    from django.apps import apps
    from django.core.mail import EmailMessage
    from django.db.models import ObjectDoesNotExist
    from django.utils import timezone

    import stripe

    from user_payments.processing import Result


    logger = logging.getLogger(__name__)


    def with_stripe_customer(payment):
        try:
            customer = payment.user.stripe_customer
        except ObjectDoesNotExist:
            return Result.FAILURE

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
            EmailMessage(str(payment), str(exc), to=[payment.email]).send(
                fail_silently=True
            )
            return Result.TERMINATE

        else:
            payment.payment_service_provider = "stripe"
            payment.charged_at = timezone.now()
            payment.transaction = json.dumps(charge)
            payment.save()

            return Result.SUCCESS


A processor which sends a "Please pay" mail
-------------------------------------------

This processor always fails, but sends a mail to the user first that
they should please pay soon-ish:

.. code-block:: python

    from django.core.mail import EmailMessage

    from user_payments.processing import Result


    def please_pay_mail(payment):
        # Each time? Each time!
        EmailMessage(str(payment), "<No body>", to=[payment.email]).send(fail_silently=True)
        return Result.FAILURE

Since this processor runs its action before returning a failure state,
it only makes sense to run this one last.


Processing individual payments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The work horse of processing is the
``user_payments.processing.process_payment`` function. The function
expects a payment instance and a list of processors and returns ``True``
if one of the individual processors returned a ``Result.SUCCESS`` state.

If all processors fail the payment is automatically canceled and the
payments' line items returned to the pool of unbound line items. This
can be changed by passing ``cancel_on_failure=False`` in case this
behavior is undesirable.


Bulk processing
~~~~~~~~~~~~~~~

The ``user_payments.processing`` module offers the following functions
to bulk process payments:

- ``process_unbound_items(processors=[...])``: Creates pending payments
  for all users with unbound line items and calls ``process_payment`` on
  them. Cancels payments if no processor succeeds.
- ``process_pending_payments(processors=[...])``: Runs all unpaid
  payments through ``process_payment``, but does not cancel a payment
  upon failure. When you're only using processors and no moochers this
  function *should* have nothing to do since ``process_unbound_items``
  always cleans up on failure. Still, it's better to be safe than sorry
  and run this function too.


Management command
~~~~~~~~~~~~~~~~~~

My recommendation is to write a management command that is run daily and
which processes unbound line items and unpaid payments. An example
management command follows:

.. code-block:: python

    from django.core.management.base import BaseCommand

    from user_payments.processing import process_unbound_items, process_pending_payments
    # Remove this line if you're not using subscriptions:
    from user_payments.user_subscriptions.models import Subscription, SubscriptionPeriod

    # Import the processors defined above
    from yourapp.processing import with_stripe_customer, please_pay_mail


    processors = [with_stripe_customer, please_pay_mail]


    class Command(BaseCommand):
        help = "Create pending payments from line items and try settling them"

        def handle(self, **options):
            # Remove those three lines if you're not using subscriptions:
            Subscription.objects.disable_autorenewal()
            Subscription.objects.create_periods()
            SubscriptionPeriod.objects.create_line_items()

            # Process payments
            process_unbound_items(processors=processors)
            process_pending_payments(processors=processors)
