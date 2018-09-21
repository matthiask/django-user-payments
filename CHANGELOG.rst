.. _changelog:

Change log
==========

`Next version`_
~~~~~~~~~~~~~~~

`0.3`_ (2018-09-21)
~~~~~~~~~~~~~~~~~~~

- Fixed the case where two consecutive ``Subscription.objects.ensure()``
  calls would lead to the subscription being restarted and a second
  period being added right away. Also, fix a bunch of other edge cases
  in ``ensure()`` and add a few additional tests while at it.
- Made it impossible to inadvertently delete subscription periods by
  cascading deletions when removing line items.
- Changed the subscription admin to only show the period inline when
  updating a subscription.
- Added ``Payment.undo()`` to undo payments which have already been
  marked as paid.
- Fixed an edge case where setting ``Subscription.paid_until`` would
  produce incorrect results when no period was paid for yet.


`0.2`_ (2018-08-05)
~~~~~~~~~~~~~~~~~~~

- Changed ``SubscriptionPeriod.objects.create_line_items()`` to only
  create line items for periods that start no later than today by
  default. A new ``until`` keyword argument allows overriding this.
- Fixed ``MANIFEST.in`` to include package data of ``stripe_customers``.
- Changed the code for the updated Stripe Python library. Updated the
  requirement for ``django-user-payments[stripe]`` to ``>=2``.
- Fixed a crash when creating a subscription with a periodicity of
  "manually" through the admin interface.


`0.1`_ (2018-06-05)
~~~~~~~~~~~~~~~~~~~

- First release that should be fit for public consumption.


.. _0.1: https://github.com/matthiask/django-user-payments/commit/c6dc9474
.. _0.2: https://github.com/matthiask/django-user-payments/compare/0.1...0.2
.. _0.3: https://github.com/matthiask/django-user-payments/compare/0.2...0.3
.. _Next version: https://github.com/matthiask/django-user-payments/compare/0.3...master
