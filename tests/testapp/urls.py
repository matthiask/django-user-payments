from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib import admin


# from testapp import views


urlpatterns = [
    url(r"^admin/", admin.site.urls),
    url(r"^moochers/", include("testapp.moochers")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
