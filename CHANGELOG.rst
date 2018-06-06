.. _changelog:

Change log
==========

`Next version`_
~~~~~~~~~~~~~~~

- Changed ``SubscriptionPeriod.objects.create_line_items()`` to only
  create line items for periods that start no later than today by
  default. A new ``until`` keyword argument allows overriding this.
- Fixed ``MANIFEST.in`` to include package data of ``stripe_customers``.


`0.1`_ (2018-06-05)
~~~~~~~~~~~~~~~~~~~

- First release that should be fit for public consumption.


.. _0.1: https://github.com/matthiask/django-user-payments/commit/c6dc9474
.. _0.2: https://github.com/matthiask/django-user-payments/compare/0.1...0.2
.. _Next version: https://github.com/matthiask/django-user-payments/compare/0.2...master
