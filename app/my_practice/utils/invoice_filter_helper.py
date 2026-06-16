"""
Invoice Filter Helper - Encapsulates invoice queryset filtering logic.
Extracts complex filter logic from InvoiceListView.get_queryset().
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import cast

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Q, QuerySet, Sum


class InvoiceFilterHelper:
    """
    Helper class to apply filters to Invoice querysets.

    Handles:
    - Search across invoice number and client fields
    - Status filtering (single and multi-status)
    - Year filtering (with status-aware date field selection)
    - Date range filtering
    - Amount range filtering
    """

    def __init__(self, queryset: QuerySet):
        """
        Initialize with base queryset.

        Args:
            queryset: Base Invoice QuerySet to filter
        """
        self.queryset = queryset

    def apply_filters(
        self,
        search_query: str | None = None,
        status_filter: str | None = None,
        multi_status: str | None = None,
        year_filter: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        min_amount: str | None = None,
        max_amount: str | None = None,
    ) -> QuerySet:
        """
        Apply all filters in sequence.

        Args:
            search_query: Search text for invoice number/client name/code
            status_filter: Single status filter (draft/sent/paid/cancelled)
            multi_status: Comma-separated status list
            year_filter: Filter by year
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            min_amount: Minimum invoice total
            max_amount: Maximum invoice total

        Returns:
            Filtered QuerySet
        """
        qs = self.queryset

        # Apply each filter
        qs = self._apply_search(qs, search_query)
        qs = self._apply_status_filter(qs, status_filter)
        qs = self._apply_multi_status(qs, multi_status)
        qs = self._apply_year_filter(qs, year_filter, status_filter)
        qs = self._apply_date_range(qs, start_date, end_date)
        qs = self._apply_amount_range(qs, min_amount, max_amount)

        return qs

    def _apply_search(self, qs: QuerySet, search_query: str | None) -> QuerySet:
        """Apply search across invoice number and client fields.

        Uses PostgreSQL full-text search (German stemming) for client name,
        and icontains for structured fields (invoice number, client code).
        """
        if not search_query or not search_query.strip():
            return qs

        query = search_query.strip()
        name_vector = SearchVector("client__full_name", config="german")
        name_q = SearchQuery(query, config="german", search_type="plain")

        return cast(
            QuerySet,
            qs.annotate(_name_rank=SearchRank(name_vector, name_q)).filter(
                Q(invoice_number__icontains=query)
                | Q(client__client_code__icontains=query)
                | Q(_name_rank__gt=0)
            ),
        )

    def _apply_status_filter(self, qs: QuerySet, status_filter: str | None) -> QuerySet:
        """Apply single status filter."""
        if not status_filter:
            return qs

        valid_statuses = ["draft", "sent", "paid", "cancelled"]
        if status_filter in valid_statuses:
            return qs.filter(status=status_filter)

        return qs

    def _apply_multi_status(self, qs: QuerySet, multi_status: str | None) -> QuerySet:
        """Apply multi-status filter (comma-separated)."""
        if not multi_status:
            return qs

        status_list = [s.strip() for s in multi_status.split(",")]
        if status_list:
            return qs.filter(status__in=status_list)

        return qs

    def _apply_year_filter(
        self, qs: QuerySet, year_filter: int | None, status_filter: str | None
    ) -> QuerySet:
        """
        Apply year filter using status-aware date field selection.

        Uses RevenueCalculator.apply_year_filter() which filters:
        - Paid invoices by paid_date
        - Other statuses by invoice_date
        """
        if not year_filter:
            return qs

        from ..utils.revenue_helpers import RevenueCalculator

        return RevenueCalculator.apply_year_filter(qs, year_filter, status_filter=status_filter)

    def _apply_date_range(
        self, qs: QuerySet, start_date: str | None, end_date: str | None
    ) -> QuerySet:
        """Apply date range filter on invoice_date."""
        if start_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                qs = qs.filter(invoice_date__gte=start)
            except ValueError:
                pass  # Invalid date format, skip filter

        if end_date:
            try:
                end = datetime.strptime(end_date, "%Y-%m-%d").date()
                qs = qs.filter(invoice_date__lte=end)
            except ValueError:
                pass  # Invalid date format, skip filter

        return qs

    def _apply_amount_range(
        self, qs: QuerySet, min_amount: str | None, max_amount: str | None
    ) -> QuerySet:
        """Apply amount range filter based on sum of invoice items.

        Uses items__total rather than the stored Invoice.total field,
        which may be stale on draft invoices that haven't been recalculated.
        """
        if not min_amount and not max_amount:
            return qs

        qs = qs.annotate(_items_total=Sum("items__total"))

        if min_amount:
            try:
                qs = qs.filter(_items_total__gte=Decimal(min_amount))
            except ValueError, TypeError, InvalidOperation:
                pass  # Invalid amount, skip filter

        if max_amount:
            try:
                qs = qs.filter(_items_total__lte=Decimal(max_amount))
            except ValueError, TypeError, InvalidOperation:
                pass  # Invalid amount, skip filter

        return qs
