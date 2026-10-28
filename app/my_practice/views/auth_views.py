"""
Sign-in with a brute-force limit and an optional second factor.

Django's LoginView accepts unlimited password guesses. For an app holding
Art. 9 health data behind a single password, that leaves an exposed instance
open to guessing at network speed. After LOGIN_FAILURE_LIMIT failed attempts
for one username from one address, further attempts — correct password
included — are refused for LOGIN_LOCKOUT_SECONDS.

Counters live in the default cache (the database cache in production, so they
are shared by every gunicorn worker and survive restarts within the window).
Behind a reverse proxy every request arrives from the proxy's address, so the
limit then effectively applies per username; that still caps guessing, at the
cost that someone hammering your username can keep you locked out for the
window.

A user who has set up an authenticator app (TwoFactorSettingsView) is not
signed in by the password alone: the login view parks them in the session and
TwoFactorVerifyView signs them in only after a valid code. Code attempts are
limited per user, so the six digits cannot be guessed either.
"""

import hashlib
import logging
import time
import unicodedata

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views import View

from ..models import TwoFactorDevice
from ..utils.two_factor import (
    generate_secret,
    new_recovery_codes,
    provisioning_uri,
    qr_svg,
    verify_second_factor,
    verify_totp,
)

logger = logging.getLogger(__name__)

LOGIN_FAILURE_LIMIT = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60
# How long the password step stays valid while the code is being typed.
PENDING_SECONDS = 5 * 60
PENDING_SESSION_KEY = "two_factor_pending"


def _throttle_key(request: HttpRequest) -> str:
    # NFKC first: AuthenticationForm's UsernameField normalizes that way before the
    # account lookup, so without it a fullwidth or other compatibility spelling
    # reaches the same account under a fresh counter.
    username = unicodedata.normalize("NFKC", request.POST.get("username", "")).strip().lower()
    address = request.META.get("REMOTE_ADDR", "")
    # Hashed so the cache table does not hold usernames in clear.
    digest = hashlib.sha256(f"{username}|{address}".encode()).hexdigest()
    return f"login-failures:{digest}"


class ThrottledLoginView(LoginView):
    """LoginView that locks a username/address pair after repeated failures."""

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if cache.get(_throttle_key(request), 0) >= LOGIN_FAILURE_LIMIT:
            logger.warning("Sign-in refused: too many failed attempts (locked out)")
            context = self.get_context_data(form=self.get_form(), login_locked=True)
            return self.render_to_response(context, status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        key = _throttle_key(self.request)
        failures = cache.get(key, 0) + 1
        cache.set(key, failures, LOGIN_LOCKOUT_SECONDS)
        if failures >= LOGIN_FAILURE_LIMIT:
            logger.warning("Sign-in locked for %s minutes", LOGIN_LOCKOUT_SECONDS // 60)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(_throttle_key(self.request))
        user = form.get_user()
        if TwoFactorDevice.objects.filter(user=user, confirmed_at__isnull=False).exists():
            # Password checked; the session is not authenticated until the code is.
            self.request.session[PENDING_SESSION_KEY] = {
                "user_id": user.pk,
                "backend": user.backend,
                "next": self.get_success_url(),
                "started": time.time(),
            }
            return redirect("login_verify")
        return super().form_valid(form)


def _code_throttle_key(user_id: int) -> str:
    return f"two-factor-failures:{user_id}"


@method_decorator(login_not_required, name="dispatch")
class TwoFactorVerifyView(View):
    """Second sign-in step: an authenticator or recovery code after the password."""

    template_name = "registration/login_verify.html"

    def _pending(self, request: HttpRequest) -> dict | None:
        pending = request.session.get(PENDING_SESSION_KEY)
        if not pending or time.time() - pending["started"] > PENDING_SECONDS:
            request.session.pop(PENDING_SESSION_KEY, None)
            return None
        return pending

    def get(self, request: HttpRequest) -> HttpResponse:
        if self._pending(request) is None:
            return redirect("login")
        return render(request, self.template_name)

    def post(self, request: HttpRequest) -> HttpResponse:
        pending = self._pending(request)
        if pending is None:
            return redirect("login")
        user = get_user_model().objects.get(pk=pending["user_id"])
        device = TwoFactorDevice.objects.get(user=user)
        key = _code_throttle_key(user.pk)

        if cache.get(key, 0) >= LOGIN_FAILURE_LIMIT:
            # Back to the password step: a locked-out attempt should not keep
            # a half-signed-in session around.
            request.session.pop(PENDING_SESSION_KEY, None)
            logger.warning("Second-factor step refused: too many failed codes (locked out)")
            return render(request, self.template_name, {"locked": True}, status=429)

        if verify_second_factor(device, request.POST.get("code", "")):
            cache.delete(key)
            request.session.pop(PENDING_SESSION_KEY, None)
            login(request, user, backend=pending["backend"])
            return redirect(pending["next"])

        failures = cache.get(key, 0) + 1
        cache.set(key, failures, LOGIN_LOCKOUT_SECONDS)
        if failures >= LOGIN_FAILURE_LIMIT:
            logger.warning("Second-factor step locked for %s minutes", LOGIN_LOCKOUT_SECONDS // 60)
        return render(request, self.template_name, {"invalid": True})


class TwoFactorSettingsView(View):
    """Set up, regenerate recovery codes for, or turn off the second factor."""

    template_name = "registration/two_factor_settings.html"

    def _context(self, request: HttpRequest, device: TwoFactorDevice | None, **extra) -> dict:
        context = {"device": device, "require_two_factor": settings.REQUIRE_TWO_FACTOR, **extra}
        if device is not None and not device.is_confirmed:
            uri = provisioning_uri(device.secret, request.user.get_username(), "My Practice")
            context["qr_svg"] = qr_svg(uri)
            context["secret_groups"] = [
                device.secret[i : i + 4] for i in range(0, len(device.secret), 4)
            ]
        if device is not None and device.is_confirmed:
            context["recovery_left"] = device.recovery_codes.filter(used_at__isnull=True).count()
        return context

    def get(self, request: HttpRequest) -> HttpResponse:
        device = TwoFactorDevice.objects.filter(user=request.user).first()
        if device is None:
            device = TwoFactorDevice.objects.create(user=request.user, secret=generate_secret())
        return render(request, self.template_name, self._context(request, device))

    def post(self, request: HttpRequest) -> HttpResponse:
        device = TwoFactorDevice.objects.filter(user=request.user).first()
        if device is None:
            return redirect("two_factor_settings")
        action = request.POST.get("action")
        code = request.POST.get("code", "")

        if action == "confirm" and not device.is_confirmed:
            if not verify_totp(device, code):
                return render(
                    request, self.template_name, self._context(request, device, code_error=True)
                )
            device.confirmed_at = timezone.now()
            device.save(update_fields=["confirmed_at", "updated_at"])
            codes = new_recovery_codes(device)
            messages.success(request, _("Two-factor sign-in is now on."))
            return render(
                request, self.template_name, self._context(request, device, recovery_codes=codes)
            )

        if action == "regenerate" and device.is_confirmed:
            if not verify_totp(device, code):
                return render(
                    request, self.template_name, self._context(request, device, code_error=True)
                )
            codes = new_recovery_codes(device)
            return render(
                request, self.template_name, self._context(request, device, recovery_codes=codes)
            )

        if action == "disable" and device.is_confirmed:
            password_ok = request.user.check_password(request.POST.get("password", ""))
            if not (password_ok and verify_second_factor(device, code)):
                return render(
                    request, self.template_name, self._context(request, device, disable_error=True)
                )
            device.delete()
            messages.success(request, _("Two-factor sign-in is now off."))
            return redirect("two_factor_settings")

        return redirect("two_factor_settings")
