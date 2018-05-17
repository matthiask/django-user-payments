from django.contrib import admin

from . import models


@admin.register(models.Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "title",
        "starts_at",
        "ends_at",
        "periodicity",
        "amount",
        "paid_until",
        "renew_automatically",
    )
    list_filter = ("renew_automatically",)
    radio_fields = {"periodicity": admin.HORIZONTAL}
    raw_id_fields = ("user",)
    search_fields = ("title",)


@admin.register(models.SubscriptionPeriod)
class SubscriptionPeriodAdmin(admin.ModelAdmin):
    list_display = ("subscription", "starts_at", "ends_at", "line_item")
    raw_id_fields = ("subscription", "line_item")
