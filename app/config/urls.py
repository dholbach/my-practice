"""
URL configuration for payments project.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from my_practice.views import serve_media

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    # Uploaded files go through an auth + ownership check in every mode — never
    # a static alias, in DEBUG or behind a web server (see media_views).
    path(f"{settings.MEDIA_URL.strip('/')}/<path:path>", serve_media, name="serve_media"),
    path("", include("my_practice.urls")),
]
