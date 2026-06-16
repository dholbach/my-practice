"""
Reusable aggregation helper functions for consistent data aggregation patterns.
"""

from decimal import Decimal
from typing import Any, cast

from django.db.models import Count, QuerySet, Sum


def get_yearly_totals(
    queryset: QuerySet,
    date_field: str = "date",
    amount_field: str = "amount",
    order: str = "desc",
) -> QuerySet:
    """
    Aggregate data by year with totals.

    Args:
        queryset: Django QuerySet to aggregate
        date_field: Name of the date field to group by (default: 'date')
        amount_field: Name of the amount field to sum (default: 'amount')
        order: Sort order - 'desc' or 'asc' (default: 'desc')

    Returns:
        QuerySet with yearly aggregations: [{date__year: int, total: Decimal}, ...]

    Example:
        yearly_totals = get_yearly_totals(CompanyExpense.objects.all())
        # Returns: [{'date__year': 2025, 'total': Decimal('50000.00')}, ...]
    """
    order_prefix = "-" if order == "desc" else ""
    year_field = f"{date_field}__year"

    return cast(
        QuerySet,
        queryset.values(year_field)
        .annotate(total=Sum(amount_field))
        .order_by(f"{order_prefix}{year_field}"),
    )


def get_category_breakdown(
    queryset: QuerySet,
    category_field: str = "category",
    amount_field: str = "amount",
    category_choices: dict[str, str] | None = None,
    order_by_total: bool = True,
) -> list[dict[str, Any]]:
    """
    Aggregate data by category with totals and counts.

    Args:
        queryset: Django QuerySet to aggregate
        category_field: Name of the category field (default: 'category')
        amount_field: Name of the amount field to sum (default: 'amount')
        category_choices: Optional dict mapping category codes to human-readable names
        order_by_total: Whether to sort by total amount (default: True)

    Returns:
        QuerySet with category aggregations including human-readable names

    Example:
        categories = get_category_breakdown(
            CompanyExpense.objects.all(),
            category_choices=dict(CompanyExpense.CATEGORY_CHOICES)
        )
        # Returns: [{'category': 'rent', 'category_name': 'Miete',
        #            'total': Decimal('24000.00'), 'count': 12}, ...]
    """
    results = queryset.values(category_field).annotate(total=Sum(amount_field), count=Count("id"))

    if order_by_total:
        results = results.order_by("-total")
    else:
        results = results.order_by(category_field)

    # Add human-readable category names
    if category_choices:
        results_list = list(results)
        for item in results_list:
            item["category_name"] = category_choices.get(item[category_field], item[category_field])
        return cast(list[dict[str, Any]], results_list)

    return cast(list[dict[str, Any]], results)


def get_monthly_breakdown(queryset, year, date_field="date", amount_field="amount"):
    """
    Aggregate data by month for a specific year.

    Args:
        queryset: Django QuerySet to aggregate
        year: Year to filter by
        date_field: Name of the date field (default: 'date')
        amount_field: Name of the amount field to sum (default: 'amount')

    Returns:
        Dict with month keys (YYYY-MM) and amounts

    Example:
        monthly = get_monthly_breakdown(CompanyWithdrawal.objects.all(), 2025)
        # Returns: {'2025-01': Decimal('5000.00'), '2025-02': Decimal('6000.00'), ...}
    """
    from collections import defaultdict

    monthly_data = defaultdict(lambda: Decimal("0"))

    monthly_items = (
        queryset.filter(**{f"{date_field}__year": year})
        .values(f"{date_field}__month", f"{date_field}__year")
        .annotate(total=Sum(amount_field))
    )

    for item in monthly_items:
        month_key = f"{item[f'{date_field}__year']}-{item[f'{date_field}__month']:02d}"
        monthly_data[month_key] = Decimal(str(item["total"]))

    return dict(monthly_data)


def get_grand_total(queryset, amount_field="amount", filter_condition=None):
    """
    Calculate grand total for a queryset with optional filtering.

    Args:
        queryset: Django QuerySet to aggregate
        amount_field: Name of the amount field to sum (default: 'amount')
        filter_condition: Optional Q object for additional filtering

    Returns:
        Decimal: Total amount

    Example:
        total = get_grand_total(CompanyExpense.objects.all())
        tax_deductible = get_grand_total(
            CompanyExpense.objects.all(),
            filter_condition=Q(is_tax_deductible=True)
        )
    """
    if filter_condition:
        queryset = queryset.filter(filter_condition)

    result = queryset.aggregate(total=Sum(amount_field))["total"]
    return result or Decimal("0")


def get_year_over_year_comparison(queryset, years, date_field="date", amount_field="amount"):
    """
    Compare aggregated totals across multiple years.

    Args:
        queryset: Django QuerySet to aggregate
        years: List of years to compare
        date_field: Name of the date field (default: 'date')
        amount_field: Name of the amount field to sum (default: 'amount')

    Returns:
        Dict with year keys and totals, plus growth percentages

    Example:
        comparison = get_year_over_year_comparison(
            Invoice.objects.filter(status='paid'),
            [2023, 2024, 2025],
            date_field='paid_date'
        )
        # Returns: {
        #     2023: {'total': Decimal('100000'), 'growth': None},
        #     2024: {'total': Decimal('120000'), 'growth': 20.0},
        #     2025: {'total': Decimal('150000'), 'growth': 25.0}
        # }
    """
    results: dict[str, Any] = {}
    previous_total: Decimal | None = None

    for year in sorted(years):
        total = queryset.filter(**{f"{date_field}__year": year}).aggregate(total=Sum(amount_field))[
            "total"
        ] or Decimal("0")

        growth = None
        prev = previous_total  # local copy for type narrowing
        if prev is not None and prev > Decimal("0"):
            growth = float((total - prev) / prev * 100)

        results[year] = {"total": total, "growth": growth}
        previous_total = total

    return results
