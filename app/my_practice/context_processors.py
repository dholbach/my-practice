import json
import logging
import re
import threading
import urllib.request

from django.conf import settings
from django.core.cache import cache
from django.db import connections

from .version import VERSION

logger = logging.getLogger(__name__)

_RELEASES_API = "https://api.github.com/repos/dholbach/my-practice/releases/latest"
_CACHE_KEY = "github_latest_release"
_LOCK_KEY = "github_latest_release_refreshing"
_CACHE_TIMEOUT = 86400  # 24 hours
# Failures are cached too, for much less time, so an unreachable GitHub is
# retried every 15 minutes rather than on every page.
_FAILURE_TIMEOUT = 900  # 15 minutes
_REQUEST_TIMEOUT = 3


def _parse_version(tag):
    """Turn a ``vX.Y.Z`` release tag into a comparable tuple of ints.

    Returns None for anything that isn't three dot-separated numbers, which the
    caller treats as "can't tell" rather than guessing.
    """
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (tag or "").strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def refresh_latest_release():
    """Look up the newest GitHub release tag and cache it ("" on failure)."""
    try:
        with urllib.request.urlopen(_RELEASES_API, timeout=_REQUEST_TIMEOUT) as resp:
            latest = json.loads(resp.read()).get("tag_name", "")
        cache.set(_CACHE_KEY, latest, _CACHE_TIMEOUT)
    except (OSError, ValueError) as exc:
        # OSError covers URLError/HTTPError/timeouts; ValueError a malformed body.
        logger.debug("Update check against %s failed: %s", _RELEASES_API, exc)
        cache.set(_CACHE_KEY, "", _FAILURE_TIMEOUT)
    finally:
        cache.delete(_LOCK_KEY)


def _refresh_in_background():
    def run():
        try:
            refresh_latest_release()
        finally:
            # The database cache opened a connection in this thread.
            connections.close_all()

    threading.Thread(target=run, name="update-check", daemon=True).start()


def update_check(request):
    """Inject update_available + latest_version when a newer release exists on GitHub.

    Skipped in DEBUG mode — dev users track git and don't need the nudge.

    A page render never waits for GitHub. On a cache miss the lookup starts in a
    background thread (one at a time, via a cache lock) and this render reports
    nothing; the next one reads the cached tag. The tag is cached for a day, a
    failed lookup as "" for 15 minutes.
    """
    if getattr(settings, "UPDATE_CHECK_DISABLED", False):
        return {}
    if settings.DEBUG:
        return {}
    if not request.user.is_authenticated:
        return {}

    latest = cache.get(_CACHE_KEY)
    if latest is None:
        # The lock outlives a hung lookup by a little, then lets the next page retry.
        if cache.add(_LOCK_KEY, True, _REQUEST_TIMEOUT * 10):
            _refresh_in_background()
        return {}

    # Compare numerically, not by inequality: between a version bump landing on
    # main and that tag actually being released, the newest *published* release
    # is older than what's running, and a string compare advertised it as an
    # upgrade ("v0.6.1 -> v0.6.0 available").
    latest_parts = _parse_version(latest)
    current_parts = _parse_version(VERSION)
    if latest_parts and current_parts and latest_parts > current_parts:
        return {"update_available": True, "current_version": VERSION, "latest_version": latest}
    return {}
