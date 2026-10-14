"""
Sign-in with a brute-force limit.

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
"""

import hashlib
import logging

from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)

LOGIN_FAILURE_LIMIT = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60


def _throttle_key(request: HttpRequest) -> str:
    username = request.POST.get("username", "").strip().lower()
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
        return super().form_valid(form)
