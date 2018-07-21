import json

from django import http
from django.apps import apps
from django.conf.urls import url
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

import stripe
from mooch.base import BaseMoocher, csrf_exempt_m, require_POST_m
from mooch.signals import post_charge

from .models import Customer


class StripeMoocher(BaseMoocher):
    identifier = "stripe"
    title = _("Pay with Stripe")

    def get_urls(self):
        return [url(r"^stripe_charge/$", self.charge_view, name="stripe_charge")]

    def payment_form(self, request, payment):
        try:
            customer = request.user.stripe_customer
        except (AttributeError, Customer.DoesNotExist):
            customer = None

        s = apps.get_app_config("stripe_customers").settings

        return render_to_string(
            "stripe_customers/payment_form.html",
            {
                "moocher": self,
                "payment": payment,
                "publishable_key": s.publishable_key,
                "customer": customer,
                "charge_url": reverse("%s:stripe_charge" % self.app_name),
                "LANGUAGE_CODE": getattr(request, "LANGUAGE_CODE", "auto"),
            },
            request=request,
        )

    @csrf_exempt_m
    @require_POST_m
    def charge_view(self, request):
        s = apps.get_app_config("user_payments").settings

        try:
            customer = request.user.stripe_customer
        except (AttributeError, Customer.DoesNotExist):
            customer = None

        instance = get_object_or_404(self.model, id=request.POST.get("id"))
        instance.payment_service_provider = self.identifier
        instance.transaction = repr(
            {key: values for key, values in request.POST.lists() if key != "token"}
        )
        instance.save()

        try:
            if (
                not customer
                and request.POST.get("token")
                and request.user.is_authenticated
            ):
                customer = Customer.objects.with_token(
                    user=request.user, token=request.POST["token"]
                )

            if customer:
                # FIXME Only with valid default source
                charge = stripe.Charge.create(
                    customer=customer.customer_id,
                    amount=instance.amount_cents,
                    currency=s.currency,
                    idempotency_key="charge-%s-%s"
                    % (instance.id.hex, instance.amount_cents),
                )
            else:
                # TODO create customer anyway, and stash away the customer ID
                # for associating with a user account after succesful payment?
                charge = stripe.Charge.create(
                    source=request.POST["token"],
                    amount=instance.amount_cents,
                    currency=s.currency,
                    idempotency_key="charge-%s-%s"
                    % (instance.id.hex, instance.amount_cents),
                )

            # TODO Error handling

            instance.charged_at = timezone.now()
            instance.transaction = json.dumps(charge)
            instance.save()

            post_charge.send(sender=self, payment=instance, request=request)

            return http.HttpResponseRedirect(self.success_url)

        except stripe.error.CardError as exc:
            messages.error(
                request, _("Card error: %s") % (exc._message or _("No details"))
            )
            return redirect(self.failure_url)
