import json
import urllib.request

from django.conf import settings
from django.core.cache import cache

from .version import VERSION

_RELEASES_API = "https://api.github.com/repos/dholbach/my-practice/releases/latest"
_CACHE_KEY = "github_latest_release"
_CACHE_TIMEOUT = 86400  # 24 hours


def update_check(request):
    """Inject update_available + latest_version when a newer release exists on GitHub.

    Skipped in DEBUG mode — dev users track git and don't need the nudge.
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
            with urllib.request.urlopen(_RELEASES_API, timeout=3) as resp:
                latest = json.loads(resp.read()).get("tag_name", "")
            cache.set(_CACHE_KEY, latest, _CACHE_TIMEOUT)
        except Exception:
            return {}

    if latest and latest != VERSION:
        return {"update_available": True, "current_version": VERSION, "latest_version": latest}
    return {}
