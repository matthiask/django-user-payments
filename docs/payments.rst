Payments
========

django-user-payments allows quickly adding line items for a user and
paying later for those.

For example, if some functionality is really expensive you might want to
add a line item each time the user requests the functionality:

.. code-block:: python

    @login_required
    def expensive_view(request):
        LineItem.objects.create(
            user=request.user,
            amount=Decimal("0.05"),
            title="expensive view at %s" % timezone.now(),
        )

        # .. further processing and response generation

At the time the user wants to pay the costs that have run up, you create
a pending payment and hand the payment off to a set of moochers:

.. code-block:: python

    @login_required
    def pay(request):
        payment = Payment.objects.create_pending(user=request.user)
        if not payment:
            # No line items, redirect somewhere else!
            return ...

        # django-mooch's Payment uses UUID4 fields:
        return redirect('pay_payment', id=payment.id.hex)


    @login_required
    def pay_payment(request, id):
        payment = get_object_or_404(
            request.user.user_payments.pending(),
            id=id,
        )
        return render(request, "pay_payment.html", {
            "payment": payment,
            "moochers": [
                moocher.payment_form(request, payment)
                for moocher in moochers.values()
            ],
        })

.. admonition:: A quick introduction to moochers

   Moochers (provided by `django-mooch
   <https://github.com/matthiask/django-mooch>`_) take a request and a
   payment instance, show a form or a button, and handle interaction
   with and responses from payment service providers. They allow
   processing individual payments one at a time.

   django-user-payments' ``Payment`` model extends the abstract
   ``mooch.Payment`` so that moochers may be readily used.


A payment life cycle
~~~~~~~~~~~~~~~~~~~~

Payments will most often be created by calling
``Payment.objects.create_pending(user=<user>)``. This creates an unpaid
payment instance and binds all unbound line items to the payment
instance by updating their ``payment`` foreign key field. The ``amount``
fields of all line items are summed up and assigned to the payments'
``amount`` field. If there were no unbound line items, no payment
instance is created and the manager method returns ``None``.

Next, the instance is hopefully processed by a moocher or
django-user-payment's processing which will be discussed later. A
paid-for payment has its nullable ``charged_at`` field (among some other
fields) set to the date and time of payment.

If payment or processing failed for some reason, the payment instance is
in most cases not very useful anymore. Deleting the instance directly
fails because the line items' ``payment`` foreign key protects against
cascading deletion. Instead, ``payment.cancel_pending()`` unbinds the
line items from the payment and deletes the payment instance.
