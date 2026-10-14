"""
URL configuration for payments project.
"""

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.decorators import login_not_required
from django.urls import include, path
from django.views.generic import RedirectView

from my_practice.views import (
    ThrottledLoginView,
    TwoFactorSettingsView,
    TwoFactorVerifyView,
    serve_media,
)

urlpatterns = [
    # The admin's own login view has neither the attempt limit nor the second
    # factor, so it would be a way around both. Send it to ours (?next= kept).
    path(
        "admin/login/",
        login_not_required(RedirectView.as_view(pattern_name="login", query_string=True)),
    ),
    path("admin/", admin.site.urls),
    # Ahead of django.contrib.auth.urls so it takes the "login" name and URL.
    path("accounts/login/", ThrottledLoginView.as_view(), name="login"),
    path("accounts/login/verify/", TwoFactorVerifyView.as_view(), name="login_verify"),
    path("accounts/two-factor/", TwoFactorSettingsView.as_view(), name="two_factor_settings"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    # Uploaded files go through an auth + ownership check in every mode — never
    # a static alias, in DEBUG or behind a web server (see media_views).
    path(f"{settings.MEDIA_URL.strip('/')}/<path:path>", serve_media, name="serve_media"),
    path("", include("my_practice.urls")),
]
