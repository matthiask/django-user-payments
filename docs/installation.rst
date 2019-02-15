Prerequisites and installation
==============================

The prerequisites for django-user-payments are:

- Django 2.2 or better
- Python 3.5 or better
- `django-mooch <https://github.com/matthiask/django-mooch>`_
  (installed as a dependency)

To install the package, start with installing the package using pip:

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
        # "user_payments.user_subscriptions",
        # "user_payments.stripe_customers",

        ...
    ]

    # Also optional, defaults:
    from datetime import timedelta  # noqa

    USER_PAYMENTS = {
        "currency": "CHF",
        "grace_period": timedelta(days=7),
        "disable_autorenewal_after": timedelta(days=15),
    }
