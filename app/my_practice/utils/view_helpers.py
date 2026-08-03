"""
Reusable view helper functions.
"""

from django.http import HttpRequest
from django.utils.http import url_has_allowed_host_and_scheme


def get_year_from_request(
    request: HttpRequest, param: str = "year", default: int | None = None
) -> int | None:
    """
    Extract year from request GET parameters.

    Args:
        request: Django request object
        param: Name of the year parameter (default: 'year')
        default: Default year if not provided

    Returns:
        int: Year or None
    """
    year_str = request.GET.get(param)

    if year_str:
        try:
            year = int(year_str)
            if 2000 <= year <= 2100:
                return year
        except ValueError:
            pass

    return default


def safe_next(request: HttpRequest, fallback: str = "/") -> str:
    """
    Return a safe redirect URL from POST['next'] or GET['next'].

    Only accepts same-host paths to prevent open-redirect attacks (rejects
    protocol-relative URLs like '//evil.com' as well as absolute URLs to
    other hosts). Falls back to `fallback` when absent or invalid.
    """
    url = request.POST.get("next") or request.GET.get("next", "")
    if url and url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return url
    return fallback
