from django.contrib import admin
from django.contrib.auth import get_user_model

from user_payments.exceptions import UnknownPeriodicity
from . import models


class SubscriptionPeriodInline(admin.TabularInline):
    model = models.SubscriptionPeriod
    raw_id_fields = ("line_item",)
    extra = 0


@admin.register(models.Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    inlines = [SubscriptionPeriodInline]
    list_display = (
        "user",
        "title",
        "code",
        "starts_on",
        "ends_on",
        "periodicity",
        "amount",
        "paid_until",
        "renew_automatically",
    )
    list_filter = ("renew_automatically", "code")
    radio_fields = {"periodicity": admin.HORIZONTAL}
    raw_id_fields = ("user",)
    search_fields = (
        "title",
        "code",
        "user__{}".format(get_user_model().USERNAME_FIELD),
    )

    def get_inline_instances(self, request, obj=None):
        if obj is None:
            return []
        return super().get_inline_instances(request, obj=obj)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            try:
                obj.create_periods()
            except UnknownPeriodicity as exc:
                self.message_user(request, exc)


@admin.register(models.SubscriptionPeriod)
class SubscriptionPeriodAdmin(admin.ModelAdmin):
    list_display = ("subscription", "starts_on", "ends_on", "line_item")
    raw_id_fields = ("subscription", "line_item")
    search_fields = [
        "subscription__{}".format(field) for field in SubscriptionAdmin.search_fields
    ]
