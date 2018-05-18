import json
import re

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _

from . import models


_sentinel = object()


def sanitize_value(matchobj):
    return "%s%s" % (matchobj.group(1), "*" * len(matchobj.group(3)))


def sanitize(data, key=_sentinel):
    if isinstance(data, dict):
        return {key: sanitize(value, key=key) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize(item) for item in data]

    if key is not _sentinel:
        if not isinstance(data, str):
            return data

        if key in ("fingerprint", "last4"):
            return "*" * len(data)

        return re.sub(r"((cus_|sub_|card_)\w{6})(\w+)", sanitize_value, data)

    return data


@admin.register(models.Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "customer_id_admin",
        "created_at",
        "updated_at",
        "active_subscriptions",
    )
    raw_id_fields = ("user",)
    search_fields = ("user__email",)

    def customer_id_admin(self, instance):
        return str(instance)

    customer_id_admin.short_description = _("customer ID")

    def customer_admin(self, instance):
        return format_html(
            '<div style="margin-left:170px"><pre>{}</pre></div>',
            json.dumps(sanitize(instance.customer), sort_keys=True, indent=4),
        )

    customer_admin.short_description = _("customer")

    def get_fields(self, request, obj=None):
        if obj is None:
            return ("user", "customer_id")
        return ("user", "created_at", "customer_id_admin", "customer_admin")

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return ("customer_id_admin", "customer_admin")
