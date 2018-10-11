from django.contrib import admin
from django.contrib.auth import get_user_model

from . import models


class LineItemInline(admin.TabularInline):
    model = models.LineItem
    raw_id_fields = ("user",)
    extra = 0


@admin.register(models.Payment)
class PaymentAdmin(admin.ModelAdmin):
    date_hierarchy = "created_at"
    inlines = [LineItemInline]
    list_display = (
        "user",
        "created_at",
        "charged_at",
        "amount",
        "payment_service_provider",
        "email",
    )
    list_filter = ("charged_at", "payment_service_provider")
    raw_id_fields = ("user",)
    search_fields = (
        "email",
        "transaction",
        "user__{}".format(get_user_model().USERNAME_FIELD),
    )


@admin.register(models.LineItem)
class LineItemAdmin(admin.ModelAdmin):
    date_hierarchy = "created_at"
    list_display = ("user", "payment", "created_at", "title", "amount")
    raw_id_fields = ("user", "payment")
    search_fields = ("title", "user__{}".format(get_user_model().USERNAME_FIELD))
