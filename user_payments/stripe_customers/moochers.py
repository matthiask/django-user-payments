import json
import time
from datetime import date, datetime
from decimal import Decimal

from django import http
from django.apps import apps
from django.conf.urls import url
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import is_safe_url
from django.utils.translation import ugettext_lazy as _

import stripe
# from app.tools.mail import render_to_mail
from mooch.base import BaseMoocher, csrf_exempt_m, require_POST_m
from mooch.signals import post_charge

from .models import Customer


login_required_m = method_decorator(login_required)


class StripeSubscriptionsMoocher(BaseMoocher):
    identifier = "stripe_customers"
    title = _("Subscribe using credit card")

    def __init__(self, *, publishable_key, secret_key, **kwargs):
        if any(x is None for x in (publishable_key, secret_key)):
            raise ImproperlyConfigured(
                "%s: None is not allowed in (%r, %r)"
                % (self.__class__.__name__, publishable_key, secret_key)
            )

        self.publishable_key = publishable_key
        self.secret_key = secret_key
        super().__init__(**kwargs)

    def get_urls(self):
        return [
            url(
                r"^stripe_customers_create/$",
                self.create_view,
                name="stripe_customers_create",
            ),
            url(
                r"^stripe_customers_webhook/$",
                self.webhook_view,
                name="stripe_customers_webook",
            ),
            url(
                r"^stripe_customers_replace_source/$",
                self.replace_source,
                name="stripe_customers_replace_source",
            ),
            url(
                r"^stripe_customers_cancel/$",
                self.cancel_subscription,
                name="stripe_customers_cancel",
            ),
        ]

    def payment_form(self, request, payment):
        try:
            customer = request.user.stripe_customer
        except Customer.DoesNotExist:
            customer = None

        return render_to_string(
            "registration/stripe_subscribe_form.html",
            {
                "moocher": self,
                "payment": payment,
                "publishable_key": self.publishable_key,
                "customer": customer,
                "create_url": reverse("%s:stripe_customers_create" % self.app_name),
                "LANGUAGE_CODE": getattr(request, "LANGUAGE_CODE", "auto"),
            },
            request=request,
        )

    @csrf_exempt_m
    @require_POST_m
    @login_required_m
    def create_view(self, request):
        instance = get_object_or_404(self.model, id=request.POST.get("id"))
        instance.payment_service_provider = self.identifier
        instance.transaction = repr(
            {key: values for key, values in request.POST.lists() if key != "token"}
        )
        instance.save()

        # Set the trial period so that users are not charged too early in
        # case they still are within a paid period.
        trial_end = None
        if (
            request.user.membership_paid_until
            and date.today() <= request.user.membership_paid_until
        ):
            trial_end = int(
                86400
                + time.mktime(
                    timezone.make_aware(
                        datetime.combine(
                            request.user.membership_paid_until, datetime.min.time()
                        )
                    ).timetuple()
                )
            )

        try:
            customer = request.user.stripe_customer
        except Customer.DoesNotExist:
            customer = None

        try:
            if request.POST.get("action") == "confirm":
                stripe.Subscription.create(
                    customer=customer.customer_id,
                    items=[{"plan": "stadtbuergerin"}],
                    trial_end=trial_end,
                )
                customer.refresh()

            elif request.POST.get("token"):
                obj = stripe.Customer.create(
                    email=instance.email,
                    source=request.POST.get("token"),
                    plan="stadtbuergerin",
                    quantity=1,
                    trial_end=trial_end,
                    expand=["default_source"],
                )
                customer = Customer.objects.create(
                    user=request.user, customer_id=obj.id, customer=obj
                )

                # TODO handle errors
                instance.transaction = repr(customer)
                instance.save()

        except stripe.CardError as exc:
            messages.error(
                request, _("Card error: %s") % (exc._message or _("No details"))
            )
            return redirect(self.failure_url)

        # TODO dirty hack. Ensures, that user can view agenda at least
        # until update_membership_paid_until runs the next time.
        if (
            not request.user.membership_paid_until
            or request.user.membership_paid_until < date.today()
        ):
            request.user.membership_paid_until = date.today()
            request.user.save()

        # post_charge.send(sender=self, payment=instance, request=request)

        return redirect(self.success_url)

    @csrf_exempt_m
    @require_POST_m
    def webhook_view(self, request):
        from pprint import pprint

        data = json.loads(request.body.decode("utf-8"))
        event = stripe.Event.retrieve(data["id"])

        pprint(event)

        if event.type == "invoice.payment_succeeded":
            try:
                customer = Customer.objects.get(customer_id=event.data.object.customer)
            except Customer.DoesNotExist:
                if event.data.object.livemode:
                    if event.data.object.customer not in [
                        # Known fails.
                        "cus_BvlAqmwTqsiwvO",
                        "cus_C5oB3eHYoISoKF",
                        "cus_CEvq0W8B0PvO73",
                        "cus_CFnxaqYQeDtZlf",
                        "cus_CTjwGXNgYsRyjc",
                        "cus_CYbHlXnRGeKAfW",
                        "cus_CYbI8egiTcBMNv",
                        "cus_CYbIDFVkCJAnHI",
                    ]:
                        raise
                # TODO Logging or something.
                return http.HttpResponse("Unknown, but OK")

            upcoming = stripe.Invoice.upcoming(customer=customer.customer_id)
            payment = self.model.objects.create(
                user=customer.user,
                period_from=timezone.make_aware(
                    datetime.fromtimestamp(upcoming.period_start)
                ),
                period_until=timezone.make_aware(
                    datetime.fromtimestamp(upcoming.period_end)
                ),
                charged_at=timezone.now(),
                payment_service_provider=self.identifier,
                email=customer.user.email,
                amount=event.data.object.total / Decimal(100),
                transaction=repr(event),
            )
            post_charge.send(sender=self, payment=payment, request=request)

        elif event.type == "invoice.payment_failed":
            customer = Customer.objects.get(customer_id=event.data.object.customer)
            render_to_mail(
                "registration/renew_failure_stripe",
                {"customer": customer},
                to=[customer.user.email],
            ).send(fail_silently=False)

        elif event.type.startswith("customer.subscription."):
            customer = Customer.objects.filter(
                customer_id=event.data.object.customer
            ).first()
            if customer:
                customer.refresh()

        elif event.type.startswith("customer.") and event.data.object.id.startswith(
            "cus_"
        ):
            customer = Customer.objects.filter(customer_id=event.data.object.id).first()
            if customer:
                customer.refresh()

        return http.HttpResponse("OK")

    @login_required_m
    def replace_source(self, request):
        try:
            customer = request.user.stripe_customer
        except Customer.DoesNotExist:
            customer = None

        if request.method == "POST":
            try:
                if customer is None:
                    obj = stripe.Customer.create(
                        email=request.user.email,
                        source=request.POST["token"],
                        expand=["default_source"],
                    )
                    Customer.objects.create(
                        user=request.user, customer_id=obj.id, customer=obj
                    )
                    messages.success(request, _("Card has been added successfully."))
                else:
                    customer.refresh(save=False)
                    customer.customer.source = request.POST["token"]
                    customer.customer.save()

                    # This time, save()!
                    customer.refresh()
                    messages.success(request, _("Card has been replaced successfully."))

            except stripe.CardError as exc:
                messages.error(
                    request, _("Card error: %s") % (exc._message or _("No details"))
                )
                return redirect(".")

            next = request.GET.get("next")
            return redirect(
                next
                if is_safe_url(next, allowed_hosts=[request.get_host()])
                else self.success_url
            )

        return render(
            request,
            "registration/replace_source.html",
            {"publishable_key": self.publishable_key, "customer": customer},
        )

    @login_required_m
    def cancel_subscription(self, request):
        customer = request.user.stripe_customer
        subscription_id = request.POST.get("subscription_id")
        if subscription_id in [
            s["id"] for s in customer.customer["subscriptions"]["data"]
        ]:

            stripe.Subscription.retrieve(subscription_id).delete(at_period_end=True)
            customer.refresh()
            messages.success(request, _("Subscription will be canceled at period end."))

        else:
            messages.error(request, _("Subscription could not be found!"))

        return redirect(self.success_url)


class StripeMoocher(BaseMoocher):
    identifier = "stripe"
    title = _("Pay with Stripe")
    use_idempotency_key = True

    def __init__(self, *, publishable_key, secret_key, **kwargs):
        if any(x is None for x in (publishable_key, secret_key)):
            raise ImproperlyConfigured(
                "%s: None is not allowed in (%r, %r)"
                % (self.__class__.__name__, publishable_key, secret_key)
            )

        self.publishable_key = publishable_key
        self.secret_key = secret_key
        super().__init__(**kwargs)

    def get_urls(self):
        return [url(r"^stripe_charge/$", self.charge_view, name="stripe_charge")]

    def payment_form(self, request, payment):
        try:
            customer = request.user.stripe_customer
        except (AttributeError, Customer.DoesNotExist):
            customer = None

        # XXX Check whether there is a valid subscription (maybe only select
        # subscriptions with monthly payment?) and add invoice items then?

        return render_to_string(
            "stripe_customers/payment_form.html",
            {
                "moocher": self,
                "payment": payment,
                "publishable_key": self.publishable_key,
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
                kw = {}
                obj = stripe.Customer.create(
                    email=request.user.email,
                    source=request.POST["token"],
                    expand=["default_source"],
                    idempotency_key="customer-%s" % request.user.id,
                    **kw
                )
                customer = Customer.objects.create(
                    user=request.user, customer_id=obj.id, customer=obj
                )

            if customer:
                # FIXME Only with valid default source
                charge = stripe.Charge.create(
                    customer=customer.customer_id,
                    amount=instance.amount_cents,
                    currency=s.currency,
                    idempotency_key="charge-%s-%s" % (customer.customer_id, instance.amount_cents),
                )
            else:
                # TODO create customer anyway, and stash away the customer ID
                # for associating with a user account after succesful payment?
                charge = stripe.Charge.create(
                    source=request.POST["token"],
                    amount=instance.amount_cents,
                    currency=s.currency,
                    idempotency_key="charge-%s-%s" % (customer.customer_id, instance.amount_cents),
                )

            # TODO Error handling

            instance.charged_at = timezone.now()
            instance.transaction = str(charge)
            instance.save()

            post_charge.send(sender=self, payment=instance, request=request)

            return http.HttpResponseRedirect(self.success_url)

        except stripe.CardError as exc:
            messages.error(
                request, _("Card error: %s") % (exc._message or _("No details"))
            )
            return redirect(self.failure_url)
