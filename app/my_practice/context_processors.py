import json
import logging
import urllib.request

from django.conf import settings
from django.core.cache import cache

from .version import VERSION

logger = logging.getLogger(__name__)

_RELEASES_API = "https://api.github.com/repos/dholbach/my-practice/releases/latest"
_CACHE_KEY = "github_latest_release"
_CACHE_TIMEOUT = 86400  # 24 hours
# Failures are cached too, for much less time. Without this, an unreachable
# GitHub means every single authenticated page render pays the full timeout
# below again — the check runs in a context processor, so it sits in the
# critical path of every response.
_FAILURE_TIMEOUT = 900  # 15 minutes
_REQUEST_TIMEOUT = 3


def update_check(request):
    """Inject update_available + latest_version when a newer release exists on GitHub.

    Skipped in DEBUG mode — dev users track git and don't need the nudge.

    The looked-up tag is cached for a day; a failed lookup is cached as an empty
    string for 15 minutes, which reads as "nothing to report" below and stops the
    next request from retrying the blocking call. Note the default cache backend
    is per-process LocMemCache, so each worker warms its own copy.
    """
    if getattr(settings, "UPDATE_CHECK_DISABLED", False):
        return {}
    if settings.DEBUG:
        return {}
    if not request.user.is_authenticated:
        return {}

    latest = cache.get(_CACHE_KEY)
    if latest is None:
        try:
            with urllib.request.urlopen(_RELEASES_API, timeout=_REQUEST_TIMEOUT) as resp:
                latest = json.loads(resp.read()).get("tag_name", "")
        except (OSError, ValueError) as exc:
            # OSError covers URLError/HTTPError/timeouts; ValueError covers a
            # malformed JSON body.
            logger.debug("Update check against %s failed: %s", _RELEASES_API, exc)
            cache.set(_CACHE_KEY, "", _FAILURE_TIMEOUT)
            return {}
        cache.set(_CACHE_KEY, latest, _CACHE_TIMEOUT)

    if latest and latest != VERSION:
        return {"update_available": True, "current_version": VERSION, "latest_version": latest}
    return {}
