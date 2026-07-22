"""
Reusable view helper functions.
"""

from django.http import HttpRequest


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

    Only accepts paths starting with '/' to prevent open-redirect attacks.
    Falls back to `fallback` when absent or invalid.
    """
    url = request.POST.get("next") or request.GET.get("next", "")
    if url and url.startswith("/"):
        return url
    return fallback
