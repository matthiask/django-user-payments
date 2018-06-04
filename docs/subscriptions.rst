Subscriptions
=============

Active subscriptions periodically create periods, which in turn create
line items.

Creating a subscription for an user looks like this:

.. code-block:: python

    subscription = Subscription.objects.ensure(
        user=request.user,
        code="the-membership",
        periodicity="monthly",
        amount=Decimal("12"),

        # Optional:
        title="The Membership",
    )

This example would also work with ``Subscription.objects.create()``, but
``Subscription.objects.ensure()`` knows to update a users' subscription
with the same ``code`` and also is smart when a subscription is updated
-- it does not only set fields, but also remove now invalid periods and
delay the new start date if the subscription is still paid for.

django-user-payments' subscriptions have no concept of a plan or a
product -- this is purely your responsibility to add (if needed).


Periods and periodicity
~~~~~~~~~~~~~~~~~~~~~~~

Next, let's add some periods and create some line items for them:

.. code-block:: python

    for period in subscription.create_periods():
        period.create_line_item()

Subscriptions are anchored on the ``starts_on`` day.  Available
periodicities are:

- ``yearly``
- ``monthly``
- ``weekly``
- ``manually``

Simply incrementing the month and year will not always work in the case
of ``yearly`` and ``monthly`` periodicity. If the naively calculated
date does not exist, the algorithm returns later dates.

.. admonition:: Specifics of recurring date calculation

   For example, if a subscription starts on 2016-02-29 (a leap year),
   the next three years' periods will start on March 1st. However, the
   period stays anchored at the start date, therefore in 2020 the period
   starts on February 29th again. Same with months: The next two period
   starts for a monthly subscription starting on 2018-03-31 will be
   2018-05-01 and 2018-05-31. As you can see, since 2018-04-31 does not
   exist, no period starts in April, and two periods start in May.

Periods end one day before the next period starts. Respectively,
subscriptions do not only offer date fields -- all date fields have a
corresponding property returning a date time in the default timezone.
Periods always start at 00:00:00 and end at 23:59:59.999999.


Subscription status and grace periods
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once line items created by subscription periods are bound to a payment
and the payment is paid for, the subscription automatically runs its
``update_paid_until()`` method. The method sets the subscriptions'
``paid_until`` date field to the date when the latest subscription
period ends.

However, the subscription status is not only determined by
``paid_until``. By default, subscriptions have a grace period of 7 days
during which the subscription is still ``subscription.is_active``, but
also ``subscription.in_grace_period``. The date time when the grace
period ends is available as ``subscription.grace_period_ends_at``.

Take note that the grace period also applies to subscriptions that have
been newly created, that is, never been paid for.

Subscriptions should be canceled by calling ``subscription.cancel()``.
This method disabled automatic renewal and removes periods and their
line items in case they haven't been paid for yet.


Periodical tasks and maintenance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The management command ``process_subscriptions`` runs the following
methods:

- ``Subscription.objects.disable_autorenewal()``: Cancel subscriptions
  that are past due by ``disable_autorenewal_after`` days, by default 15
  days.
- ``Subscription.objects.create_periods()``: Run
  ``subscription.create_periods()`` on all subscriptions that should
  renew automatically.
- ``SubscriptionPeriod.objects.create_line_items()``: Make periods
  create their line items in case they haven't done so already.


Closing notes
~~~~~~~~~~~~~

As you can see subscriptions do not concern themselves with payment
processing, only with creating line items. Subscriptions only use
payments to automatically update their ``paid_until`` date field.
