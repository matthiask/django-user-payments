from collections import OrderedDict

from django.conf.urls import include, url

from user_payments.models import Payment
from user_payments.stripe_customers.moochers import StripeMoocher


app_name = "mooch"
moochers = OrderedDict([("stripe", StripeMoocher(model=Payment, app_name=app_name))])
urlpatterns = [url(r"", include(moocher.urls)) for moocher in moochers.values()]
