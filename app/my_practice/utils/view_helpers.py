"""
Reusable view helper functions.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from django.db.models import Q, QuerySet
from django.http import HttpRequest

if TYPE_CHECKING:
    from django.core.paginator import Page, Paginator  # noqa: F401 — used in return type annotation


def get_date_range_from_request(
    request: HttpRequest, start_param: str = "start_date", end_param: str = "end_date"
) -> tuple[date | None, date | None]:
    """
    Extract and validate date range from request GET parameters.

    Args:
        request: Django request object
        start_param: Name of the start date parameter (default: 'start_date')
        end_param: Name of the end date parameter (default: 'end_date')

    Returns:
        tuple: (start_date, end_date) or (None, None) if invalid
    """
    start_str = request.GET.get(start_param)
    end_str = request.GET.get(end_param)

    start_date = None
    end_date = None

    if start_str:
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    if end_str:
        try:
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    return start_date, end_date


def filter_queryset_by_date_range(
    queryset: QuerySet,
    date_field: str,
    start_date: date | None,
    end_date: date | None,
) -> QuerySet:
    """
    Apply date range filter to a queryset.

    Args:
        queryset: Django QuerySet
        date_field: Name of the date field to filter on
        start_date: Start date (can be None)
        end_date: End date (can be None)

    Returns:
        QuerySet: Filtered queryset
    """
    if start_date:
        queryset = queryset.filter(**{f"{date_field}__gte": start_date})

    if end_date:
        queryset = queryset.filter(**{f"{date_field}__lte": end_date})

    return queryset


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


def paginate_queryset(
    request: HttpRequest, queryset: QuerySet, per_page: int = 20
) -> tuple["Page", "Paginator"]:
    """
    Paginate a queryset based on request parameters.

    Args:
        request: Django request object
        queryset: QuerySet to paginate
        per_page: Items per page (default: 20)

    Returns:
        tuple: (page_obj, paginator)
    """
    from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

    page = request.GET.get("page", 1)
    paginator = Paginator(queryset, per_page)

    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return page_obj, paginator


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


def get_search_query_filter(search_query: str | None, fields: list[str]) -> Q:
    """
    Build a Q object for searching across multiple fields.

    Args:
        search_query: Search string
        fields: List of field names to search in (icontains)

    Returns:
        Q: Django Q object for filtering
    """
    if not search_query:
        return Q()

    q_objects = Q()
    for field in fields:
        q_objects |= Q(**{f"{field}__icontains": search_query})

    return q_objects
