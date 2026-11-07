"""
Failed-attempt counters for the sign-in and second-factor steps.

Kept in the LoginThrottle table, not the cache, so no amount of unrelated
traffic can evict a counter before its window ends. Each failure renews the
window, as the cache timeout used to.

Rows an unauthenticated client can create are bounded by time, not by count:
each one costs a full password hash (about 0.2 s), and every failure deletes
the rows whose window has ended, so the table holds at most one window's worth
of attempts. Capping the count would bring eviction back.
"""

from datetime import timedelta

from django.db.models import Case, F, Value, When
from django.utils import timezone

from ..models import LoginThrottle


def failure_count(key: str) -> int:
    """Failures recorded for ``key`` in its current window (0 once it has expired)."""
    row = LoginThrottle.objects.filter(key=key, expires_at__gt=timezone.now()).first()
    return row.failures if row else 0


def record_failure(key: str, window_seconds: int) -> int:
    """Count one more failure for ``key``, renew its window, and return the new count."""
    now = timezone.now()
    expires_at = now + timedelta(seconds=window_seconds)
    LoginThrottle.objects.filter(expires_at__lte=now).delete()
    row, created = LoginThrottle.objects.get_or_create(
        key=key, defaults={"failures": 1, "expires_at": expires_at}
    )
    if not created:
        # One UPDATE, so two failures arriving together both count.
        LoginThrottle.objects.filter(pk=row.pk).update(
            failures=Case(When(expires_at__gt=now, then=F("failures") + 1), default=Value(1)),
            expires_at=expires_at,
        )
        row.refresh_from_db(fields=["failures"])
    return row.failures


def clear_failures(key: str) -> None:
    """Forget the failures for ``key`` after a successful attempt."""
    LoginThrottle.objects.filter(key=key).delete()
