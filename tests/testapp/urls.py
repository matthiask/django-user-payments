from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


# from testapp import views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("moochers/", include("testapp.moochers")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
