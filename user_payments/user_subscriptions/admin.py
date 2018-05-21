from django.contrib import admin

from . import models


@admin.register(models.Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "title",
        "starts_on",
        "ends_on",
        "periodicity",
        "amount",
        "paid_until",
        "renew_automatically",
    )
    list_filter = ("renew_automatically",)
    radio_fields = {"periodicity": admin.HORIZONTAL}
    raw_id_fields = ("user",)
    search_fields = ("title",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            obj.create_periods()


@admin.register(models.SubscriptionPeriod)
class SubscriptionPeriodAdmin(admin.ModelAdmin):
    list_display = ("subscription", "starts_on", "ends_on", "line_item")
    raw_id_fields = ("subscription", "line_item")
