"""
Financial List Context Builder - Shared logic for expense/withdrawal list views.
Eliminates duplication in context preparation for financial tracking views.
"""

from datetime import date
from typing import Any

from django.db.models import Q, QuerySet


class FinancialListContextBuilder:
    """
    Build context data for financial list views (expenses, withdrawals).

    Handles:
    - Year filtering
    - Yearly aggregations
    - Category/monthly breakdowns
    - Grand totals
    - Tax deductible calculations (for expenses)
    """

    def __init__(self, queryset: QuerySet, year_filter: int | None = None):
        """
        Initialize builder with base queryset and optional year filter.

        Args:
            queryset: Base QuerySet (e.g., CompanyExpense.objects.all())
            year_filter: Optional year to filter by
        """
        self.base_queryset = queryset
        self.year_filter = year_filter
        self.model = queryset.model

    def build_context(
        self,
        include_categories: bool = False,
        include_monthly: bool = False,
        include_tax_deductible: bool = False,
        limit: int | None = None,
    ) -> tuple[dict[str, Any], QuerySet]:
        """
        Build complete context dictionary for template.

        Args:
            include_categories: Whether to include category breakdown
            include_monthly: Whether to include monthly breakdown for current year
            include_tax_deductible: Whether to include tax deductible total
            limit: Limit number of items returned (for pagination)

        Returns:
            Dictionary with all context data
        """
        from ..utils.aggregation_helpers import (
            get_grand_total,
            get_yearly_totals,
        )

        # Apply year filter if provided
        filtered_qs = self._apply_year_filter()

        # Get ordered items
        items = filtered_qs.order_by("-date")
        if limit:
            items = items[:limit]

        # Build base context
        context = {
            "yearly_totals": get_yearly_totals(self.base_queryset),
            "grand_total": get_grand_total(
                self.base_queryset
            ),  # Always show total across all years
        }

        # Add filtered total if year filter is active
        if self.year_filter:
            context["filtered_total"] = get_grand_total(filtered_qs)

        # Add optional sections
        if include_categories:
            context["category_totals"] = self._get_category_breakdown(filtered_qs)

        if include_monthly:
            context["monthly_data"] = self._get_monthly_breakdown(filtered_qs)

        if include_tax_deductible:
            context["tax_deductible_total"] = get_grand_total(
                filtered_qs, filter_condition=Q(is_tax_deductible=True)
            )

        # Add year filter to context if active
        if self.year_filter:
            context["selected_year"] = self.year_filter

        return context, items

    def _apply_year_filter(self) -> QuerySet:
        """Apply year filter to base queryset if specified."""
        if self.year_filter:
            return self.base_queryset.filter(date__year=self.year_filter)
        return self.base_queryset

    def _get_category_breakdown(self, queryset: QuerySet) -> list[dict[str, Any]]:
        """Get category breakdown with human-readable names."""
        from ..utils.aggregation_helpers import get_category_breakdown

        # Get CATEGORY_CHOICES from model if it exists
        category_choices = getattr(self.model, "CATEGORY_CHOICES", None)
        if category_choices:
            category_dict = dict(category_choices)
            return get_category_breakdown(queryset, category_choices=category_dict)

        return get_category_breakdown(queryset)

    def _get_monthly_breakdown(self, queryset: QuerySet) -> dict[str, Any]:
        """Get monthly breakdown for current year."""
        from ..utils.aggregation_helpers import get_monthly_breakdown

        current_year = date.today().year
        monthly_data = get_monthly_breakdown(queryset, current_year)
        return dict(monthly_data)
