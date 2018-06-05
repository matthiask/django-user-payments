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


Bundled processors
~~~~~~~~~~~~~~~~~~

- ``user_payments.processing.please_pay_mail``: Sends the user a mail
  that payment is due and returns a failure result. This processor will
  probably most often be added as the last entry in the processors list.
- ``user_payments.stripe_customers.processing.with_stripe_customer``:
  Tries charging the users' credit card using Stripe. If a Stripe
  customer exists but their card could not be charged for some reason,
  this processor sends a mail and terminates further processing for this
  payment, so that e.g. the ``please_pay_mail`` does not send another
  mail.

.. warning::

   Instead of sending a mail we will probably dispatch a signal in the
   near future.

By default, only the ``please_pay_mail`` is activated. To activate both,
add ``"user_payments.stripe_customers"`` to ``INSTALLED_APPS`` and add
at least the following ``USER_PAYMENTS`` setting:

.. code-block:: python

    USER_PAYMENTS = {
        "processors": [
            "user_payments.stripe_customers.processing.with_stripe_customer",
            "user_payments.processing.please_pay_mail"
        ],
    }


Processing individual payments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The work horse of processing is the
``user_payments.processing.process_payment`` function. The function
expects a payment instance and returns ``True`` if one of the individual
processors returned a ``Result.SUCCESS`` state.

The list of processors can be overridden by passing a list of callables
as ``processors=[...]``. If all processors fail the payment is
automatically canceled and the payments' line items returned to the pool
of unbound line items. This can be changed by passing
``cancel_on_failure=False`` in case this behavior is undesirable.


Management command
~~~~~~~~~~~~~~~~~~

The management command ``process_payments`` runs the following
functions from the ``user_payments.processing`` module:

- ``process_unbound_items``: Creates a pending payment for all users
  with unbound line items and sends the payment through
  ``process_payment``. Unsuccessful payments are canceled and removed.
- ``process_pending_payments``: Runs all payments through
  ``process_payment``, but does not cancel a payment upon failure.


Logging
~~~~~~~

django-user-payments' processing framework emits many log messages. You
probably want to configure a logger for ``"user_payments"``.
