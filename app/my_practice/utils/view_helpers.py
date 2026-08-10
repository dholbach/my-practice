"""
Reusable view helper functions.
"""

from typing import Any, Callable

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
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


def get_object_or_403(
    model: Any,
    request: HttpRequest,
    practice_getter: Callable[[Any], Any] | None = None,
    **lookup: Any,
) -> Any:
    """
    Fetch an object by `lookup`, then enforce it belongs to the current practice.

    Raises Http404 if no object matches `lookup`, or PermissionDenied if it
    exists but belongs to a different practice. `practice_getter` extracts the
    practice from the object; defaults to `obj.practice` — pass e.g.
    `lambda doc: doc.client.practice` when the model has no direct FK.

    Example:
        doc = get_object_or_403(ClientDocument, request, pk=pk, practice_getter=lambda d: d.client.practice)
        expense = get_object_or_403(CompanyExpense, request, pk=pk)
    """
    obj = get_object_or_404(model, **lookup)
    practice = practice_getter(obj) if practice_getter else obj.practice
    if practice != request.current_practice:
        raise PermissionDenied
    return obj
