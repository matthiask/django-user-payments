from collections import OrderedDict

from django.conf.urls import include, url

from user_payments.models import Payment
from user_payments.stripe_customers.moochers import StripeMoocher


kw = {"model": Payment, "app_name": "mooch"}

moochers = OrderedDict(
    [("stripe", StripeMoocher(publishable_key="pk", secret_key="sk", **kw))]
)

app_name = "mooch"
urlpatterns = [url(r"", include(moocher.urls)) for moocher in moochers.values()]
