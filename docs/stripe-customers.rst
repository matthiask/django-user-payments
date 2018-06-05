Stripe customers
================

The Stripe customers module offers a moocher which automatically creates
a `Stripe customer <https://stripe.com/docs/api/python#customers>`_, a
model which binds Stripe customers to user instances and a processor for
payments.

.. note::

   Stripe supports more than one source (that is, credit card) per
   customer, but our ``user_payments.stripe_customers`` module does not.

The Stripe customers app requires ``STRIPE_PUBLISHABLE_KEY`` and
``STRIPE_SECRET_KEY`` settings.


The moocher
~~~~~~~~~~~

The ``user_payments.stripe_customers.moochers.StripeMoocher`` is
basically a drop-in replacement for django-mooch's
``mooch.stripe.StripeMoocher``, except for:

- Instead of only charging the user once, our moocher creates a Stripe
  customer and binds it to a local Django user (in case the user is
  authenticated) to make future payments less cumbersome.
- If an authenticated user already has a Stripe customer, the moocher
  only shows basic credit card information (e.g. the brand and expiry
  date) and a "Pay" button instead of requiring entry of all numbers
  again.
