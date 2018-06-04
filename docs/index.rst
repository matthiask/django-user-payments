==================================================================
django-user-payments -- Create, track and settle payments by users
==================================================================

Version |release|

django-user-payments consists of a few modules which help with managing
payments and subscriptions by users on a Django-based site.

Prerequisites
=============

- Django 1.11 or better
- Python 3.5 or better (3.4 may work, but is not tested)
- `django-mooch <https://github.com/matthiask/django-mooch>`_
  (automatically installed)


Installation
============

Install the package:

.. code-block:: bash

    pip install django-user-payments

Add the apps to ``INSTALLED_APPS`` and override settings if you want to
change the defaults:

.. code-block:: python

    INSTALLED_APPS = [
        ...

        # Required:
        "user_payments",

        # Optional, if you want those features:
        "user_payments.user_subscriptions",
        "user_payments.stripe_customers",

        ...
    ]

    # Also optional, defaults:
    from datetime import timedelta  # noqa

    USER_PAYMENTS = {
        "currency": "CHF",
        "grace_period": timedelta(days=7),
        "disable_autorenewal_after": timedelta(days=15),
        "processors": [
            # "user_payments.stripe_customers.processing.with_stripe_customer",
            "user_payments.processing.send_notification_mail"
        ],
    }


Table of Contents
=================

.. toctree::
   :maxdepth: 2

   payments
   subscriptions
   stripe-customers
   processing


.. include:: ../CHANGELOG.rst

.. _Pillow: https://pillow.readthedocs.io/en/latest/
