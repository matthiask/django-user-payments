from datetime import datetime
from decimal import Decimal

from django import template
from django.utils.timezone import make_aware


register = template.Library()


@register.filter
def fromtimestamp(timestamp):
    return make_aware(datetime.utcfromtimestamp(timestamp))


@register.filter
def fromcents(amount):
    return amount / Decimal("100.00")
