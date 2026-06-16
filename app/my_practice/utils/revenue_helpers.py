"""
Revenue calculation utilities.
Centralized logic for revenue aggregations and statistics.
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db.models import (
    Avg,
    Count,
    F,
    FloatField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Sum,
)
from django.db.models.functions import Cast

if TYPE_CHECKING:
    from ..models import Practice, Client

from ..models import Invoice, InvoiceItem


class RevenueCalculator:
    """
    Centralized revenue calculations with consistent filters.

    All methods use 'status="paid"' filter by default to ensure
    only paid invoices are counted in revenue calculations.
    """

    @staticmethod
    def build_paid_date_filter(year: int, month: int | None = None) -> Q:
        """
        Build Q object for filtering by paid_date with invoice_date fallback.

        For tax accuracy: includes invoices paid in the specified period,
        or with null paid_date but invoice_date in that period.

        Args:
            year: Year to filter by
            month: Optional month (1-12). If None, filters by year only.

        Returns:
            Q: Django Q object for filtering

        Example:
            >>> qs = Invoice.objects.filter(
            ...     RevenueCalculator.build_paid_date_filter(2026, 1),
            ...     status="paid"
            ... )
        """
        if month is not None:
            return Q(paid_date__year=year, paid_date__month=month) | Q(
                paid_date__isnull=True,
                invoice_date__year=year,
                invoice_date__month=month,
            )
        else:
            return Q(paid_date__year=year) | Q(paid_date__isnull=True, invoice_date__year=year)

    @staticmethod
    def build_paid_date_range_filter(start_date, end_date) -> Q:
        """
        Build Q object for filtering by paid_date within a date range, with
        invoice_date fallback for invoices where paid_date is null.

        Args:
            start_date: Inclusive start date
            end_date: Inclusive end date

        Returns:
            Q: Django Q object for filtering
        """
        return Q(paid_date__gte=start_date, paid_date__lte=end_date) | Q(
            paid_date__isnull=True,
            invoice_date__gte=start_date,
            invoice_date__lte=end_date,
        )

    @staticmethod
    def get_client_revenue_subquery() -> Subquery:
        """
        Get a Subquery for safely aggregating client revenue.

        Use this in annotate() to avoid JOIN multiplication when combining
        with other aggregations (e.g., session counts from invoice items).

        Returns:
            Subquery: For use in Client.objects.annotate(total_revenue=...)

        Example:
            >>> from django.db.models import OuterRef
            >>> Client.objects.annotate(
            ...     total_revenue=RevenueCalculator.get_client_revenue_subquery()
            ... )

        See Also:
            - docs/BUGFIX_CLIENT_REVENUE_2026-01-06.md for background
            - get_client_sessions_subquery() for session counting
        """
        paid_invoice_subquery = Invoice.objects.filter(client=OuterRef("pk"), status="paid")
        return Subquery(
            paid_invoice_subquery.values("client").annotate(total=Sum("total")).values("total")[:1]
        )

    @staticmethod
    def get_client_sessions_subquery(exclude_cancellations: bool = True) -> Subquery:
        """
        Get a Subquery for safely counting client sessions.

        Use this in annotate() to avoid JOIN multiplication when combining
        with invoice-level aggregations.

        Sessions are calculated using the formula: (duration / 60) * quantity
        This normalizes all sessions to a 60-minute base.

        Args:
            exclude_cancellations: If True, excludes items whose service_type code contains "cancel"

        Returns:
            Subquery: For use in Client.objects.annotate(total_sessions=...)

        Example:
            >>> Client.objects.annotate(
            ...     total_sessions=RevenueCalculator.get_client_sessions_subquery()
            ... )
        """
        paid_item_subquery = InvoiceItem.objects.filter(
            invoice__client=OuterRef("pk"), invoice__status="paid"
        )

        if exclude_cancellations:
            paid_item_subquery = paid_item_subquery.exclude(service_type__code__icontains="cancel")

        return Subquery(
            paid_item_subquery.values("invoice__client")
            .annotate(
                total=Sum(
                    Cast(F("session__duration"), FloatField())
                    / 60.0
                    * Cast(F("quantity"), FloatField())
                )
            )
            .values("total")[:1]
        )

    @staticmethod
    def apply_year_filter(
        queryset: QuerySet[Invoice],
        year: int,
        status_filter: str | None = None,
    ) -> QuerySet[Invoice]:
        """
        Apply year-aware filtering to an Invoice queryset.

        For paid invoices, filters by paid_date (when payment was received).
        For other statuses, filters by invoice_date (when invoice was created).

        Args:
            queryset: The base Invoice queryset
            year: The year to filter by
            status_filter: Optional status to determine which date field to use.
                          If None, uses Q objects for mixed filtering.

        Returns:
            QuerySet: Filtered queryset

        Example:
            >>> qs = Invoice.objects.all()
            >>> RevenueCalculator.apply_year_filter(qs, 2026, status_filter="paid")
            # Returns invoices where paid_date is in 2026
        """
        if status_filter == "paid":
            # Paid invoices: filter by paid_date
            return queryset.filter(paid_date__year=year)
        elif status_filter in ["draft", "sent", "cancelled"]:
            # Other statuses: filter by invoice_date
            return queryset.filter(invoice_date__year=year)
        else:
            # Mixed or no status filter: use Q objects
            # Paid invoices by paid_date, others by invoice_date
            return queryset.filter(
                Q(status="paid", paid_date__year=year)
                | Q(~Q(status="paid"), invoice_date__year=year)
            )

    @staticmethod
    def get_total_revenue(filters: dict[str, Any] | None = None) -> Decimal:
        """
        Get total revenue for paid invoices with optional additional filters.

        Args:
            filters: dict of additional filter kwargs (e.g., {'client': client})

        Returns:
            Decimal: Total revenue amount

        Example:
            >>> RevenueCalculator.get_total_revenue()
            Decimal('12580.00')
            >>> RevenueCalculator.get_total_revenue({'paid_date__year': 2025})
            Decimal('4200.00')
        """
        qs = Invoice.objects.filter(status="paid")
        if filters:
            qs = qs.filter(**filters)
        result = qs.aggregate(revenue_total=Sum("total"))["revenue_total"]
        return result if result is not None else Decimal("0")

    @staticmethod
    def get_revenue_stats(
        filters: dict[str, Any] | None = None, include_avg: bool = True
    ) -> dict[str, Any]:
        """
        Get comprehensive revenue statistics (total, count, optional avg).

        Args:
            filters: dict of additional filter kwargs
            include_avg: whether to include average calculation

        Returns:
            dict: {
                'total': Decimal,
                'count': int,
                'avg': Decimal (if include_avg=True)
            }

        Example:
            >>> RevenueCalculator.get_revenue_stats({'client': client})
            {'total': Decimal('2800.00'), 'count': 14, 'avg': Decimal('200.00')}
        """
        qs = Invoice.objects.filter(status="paid")
        if filters:
            qs = qs.filter(**filters)

        aggregations = {
            "revenue_total": Sum("total"),
            "invoice_count": Count("id"),
        }

        if include_avg:
            aggregations["revenue_avg"] = Avg("total")

        stats = qs.aggregate(**aggregations)

        return {
            "total": (
                stats["revenue_total"] if stats["revenue_total"] is not None else Decimal("0")
            ),
            "count": stats["invoice_count"] or 0,
            "avg": (
                stats.get("revenue_avg") if stats.get("revenue_avg") is not None else Decimal("0")
            ),
        }

    @staticmethod
    def get_year_revenue(
        year: int, use_paid_date: bool = True, practice: "Practice" | None = None
    ) -> dict[str, Any]:
        """
        Get revenue statistics for a specific year.

        Args:
            year: int year (e.g., 2025)
            use_paid_date: if True, use paid_date; if False, use invoice_date
            practice: Practice instance for multi-practice filtering

        Returns:
            dict: {
                'total': Decimal,
                'count': int,
                'avg': Decimal
            }

        Example:
            >>> RevenueCalculator.get_year_revenue(2025)
            {'total': Decimal('4200.00'), 'count': 21, 'avg': Decimal('200.00')}
        """
        qs = Invoice.objects.filter(status="paid")

        if practice:
            qs = qs.filter(practice=practice)

        if use_paid_date:
            qs = qs.filter(RevenueCalculator.build_paid_date_filter(year))
        else:
            qs = qs.filter(invoice_date__year=year)

        stats = qs.aggregate(
            revenue_total=Sum("total"),
            invoice_count=Count("id"),
            revenue_avg=Avg("total"),
        )

        return {
            "total": (
                stats["revenue_total"] if stats["revenue_total"] is not None else Decimal("0")
            ),
            "count": stats["invoice_count"] or 0,
            "avg": (stats["revenue_avg"] if stats["revenue_avg"] is not None else Decimal("0")),
        }

    @staticmethod
    def get_month_revenue(
        year: int,
        month: int,
        use_paid_date: bool = True,
        practice: "Practice" | None = None,
    ) -> dict[str, Any]:
        """
        Get revenue statistics for a specific month.

        Args:
            year: int year (e.g., 2025)
            month: int month (1-12)
            use_paid_date: if True, use paid_date; if False, use invoice_date
            practice: Practice instance for multi-practice filtering

        Returns:
            dict: {
                'total': Decimal,
                'count': int,
                'avg': Decimal
            }

        Example:
            >>> RevenueCalculator.get_month_revenue(2025, 12)
            {'total': Decimal('420.00'), 'count': 3, 'avg': Decimal('140.00')}
        """
        qs = Invoice.objects.filter(status="paid")

        if practice:
            qs = qs.filter(practice=practice)

        if use_paid_date:
            qs = qs.filter(RevenueCalculator.build_paid_date_filter(year, month))
        else:
            qs = qs.filter(invoice_date__year=year, invoice_date__month=month)

        stats = qs.aggregate(
            revenue_total=Sum("total"),
            invoice_count=Count("id"),
            revenue_avg=Avg("total"),
        )

        return {
            "total": (
                stats["revenue_total"] if stats["revenue_total"] is not None else Decimal("0")
            ),
            "count": stats["invoice_count"] or 0,
            "avg": (stats["revenue_avg"] if stats["revenue_avg"] is not None else Decimal("0")),
        }

    @staticmethod
    def get_client_revenue(client: "Client", include_unpaid: bool = False) -> dict[str, Any]:
        """
        Get revenue statistics for a specific client.

        Args:
            client: Client object
            include_unpaid: if True, include all invoice statuses

        Returns:
            dict: {
                'total': Decimal,
                'count': int,
                'avg': Decimal
            }

        Example:
            >>> client = Client.objects.get(client_code="BK")
            >>> RevenueCalculator.get_client_revenue(client)
            {'total': Decimal('2800.00'), 'count': 14, 'avg': Decimal('200.00')}
        """
        filters = {"client": client}
        if not include_unpaid:
            # Default: only paid invoices
            return RevenueCalculator.get_revenue_stats(filters)
        else:
            # Include all statuses
            qs = Invoice.objects.filter(**filters)
            stats = qs.aggregate(
                revenue_total=Sum("total"),
                invoice_count=Count("id"),
                revenue_avg=Avg("total"),
            )
            return {
                "total": (
                    stats["revenue_total"] if stats["revenue_total"] is not None else Decimal("0")
                ),
                "count": stats["invoice_count"] or 0,
                "avg": (stats["revenue_avg"] if stats["revenue_avg"] is not None else Decimal("0")),
            }

    @staticmethod
    def get_status_breakdown(
        filters: dict | None = None, year: int | None = None
    ) -> dict[str, dict[str, Any]]:
        """
        Get invoice counts and totals broken down by status.

        Uses conditional aggregation for performance. When a year is specified,
        draft/sent/cancelled are filtered by invoice_date, but paid invoices
        are filtered by paid_date (when they were actually paid).

        Args:
            filters: dict of additional filter kwargs (applied to all statuses)
            year: int year to filter by (uses paid_date for paid invoices)

        Returns:
            dict: {
                'draft': {'count': int, 'total': Decimal},
                'sent': {'count': int, 'total': Decimal},
                'paid': {'count': int, 'total': Decimal},
                'cancelled': {'count': int, 'total': Decimal}
            }

        Example:
            >>> RevenueCalculator.get_status_breakdown()
            {
                'draft': {'count': 5, 'total': Decimal('500.00')},
                'sent': {'count': 3, 'total': Decimal('300.00')},
                'paid': {'count': 120, 'total': Decimal('12580.00')},
                'cancelled': {'count': 2, 'total': Decimal('200.00')}
            }
        """
        from django.db.models import Case, When

        if year:
            # For year filtering: use invoice_date for draft/sent/cancelled,
            # but paid_date for paid invoices (when payment was received)
            qs_invoice_date = Invoice.objects.filter(invoice_date__year=year)
            if filters:
                # Remove invoice_date__year from filters if present (we handle it separately)
                filters_copy = {k: v for k, v in filters.items() if k != "invoice_date__year"}
                if filters_copy:
                    qs_invoice_date = qs_invoice_date.filter(**filters_copy)

            # Query for draft/sent/cancelled (by invoice_date)
            stats_by_invoice_date = qs_invoice_date.aggregate(
                draft_count=Count(Case(When(status="draft", then=1))),
                draft_total=Sum(Case(When(status="draft", then="total"))),
                sent_count=Count(Case(When(status="sent", then=1))),
                sent_total=Sum(Case(When(status="sent", then="total"))),
                cancelled_count=Count(Case(When(status="cancelled", then=1))),
                cancelled_total=Sum(Case(When(status="cancelled", then="total"))),
            )

            # Query for paid (by paid_date - when the payment was received)
            qs_paid_date = Invoice.objects.filter(status="paid", paid_date__year=year)
            if filters:
                filters_copy = {k: v for k, v in filters.items() if k != "invoice_date__year"}
                if filters_copy:
                    qs_paid_date = qs_paid_date.filter(**filters_copy)

            stats_by_paid_date = qs_paid_date.aggregate(
                paid_count=Count("id"),
                paid_total=Sum("total"),
            )

            return {
                "draft": {
                    "count": stats_by_invoice_date["draft_count"],
                    "total": (
                        stats_by_invoice_date["draft_total"]
                        if stats_by_invoice_date["draft_total"] is not None
                        else Decimal("0")
                    ),
                },
                "sent": {
                    "count": stats_by_invoice_date["sent_count"],
                    "total": (
                        stats_by_invoice_date["sent_total"]
                        if stats_by_invoice_date["sent_total"] is not None
                        else Decimal("0")
                    ),
                },
                "paid": {
                    "count": stats_by_paid_date["paid_count"],
                    "total": (
                        stats_by_paid_date["paid_total"]
                        if stats_by_paid_date["paid_total"] is not None
                        else Decimal("0")
                    ),
                },
                "cancelled": {
                    "count": stats_by_invoice_date["cancelled_count"],
                    "total": (
                        stats_by_invoice_date["cancelled_total"]
                        if stats_by_invoice_date["cancelled_total"] is not None
                        else Decimal("0")
                    ),
                },
            }

        # No year filter - use single query with conditional aggregation
        qs = Invoice.objects.all()
        if filters:
            qs = qs.filter(**filters)

        stats = qs.aggregate(
            draft_count=Count(Case(When(status="draft", then=1))),
            draft_total=Sum(Case(When(status="draft", then="total"))),
            sent_count=Count(Case(When(status="sent", then=1))),
            sent_total=Sum(Case(When(status="sent", then="total"))),
            paid_count=Count(Case(When(status="paid", then=1))),
            paid_total=Sum(Case(When(status="paid", then="total"))),
            cancelled_count=Count(Case(When(status="cancelled", then=1))),
            cancelled_total=Sum(Case(When(status="cancelled", then="total"))),
        )

        return {
            "draft": {
                "count": stats["draft_count"],
                "total": (
                    stats["draft_total"] if stats["draft_total"] is not None else Decimal("0")
                ),
            },
            "sent": {
                "count": stats["sent_count"],
                "total": (stats["sent_total"] if stats["sent_total"] is not None else Decimal("0")),
            },
            "paid": {
                "count": stats["paid_count"],
                "total": (stats["paid_total"] if stats["paid_total"] is not None else Decimal("0")),
            },
            "cancelled": {
                "count": stats["cancelled_count"],
                "total": (
                    stats["cancelled_total"]
                    if stats["cancelled_total"] is not None
                    else Decimal("0")
                ),
            },
        }
