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
