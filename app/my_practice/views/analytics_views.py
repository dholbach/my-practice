"""
Analytics views for the payments application.
"""

from decimal import Decimal
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from ..models import Invoice
from ..utils import AnalyticsDashboardBuilder, RevenueCalculator
from ..utils.practice_analysis import PracticeAnalyzer, calculate_quarter_trends
from ..utils.view_helpers import get_year_from_request


def practice_analysis_redirect(request: HttpRequest) -> HttpResponse:
    """Redirect from old practice_analysis URL to unified analytics with capacity tab.

    P-004: practice_analysis was merged into analytics_dashboard.
    This provides backwards compatibility for bookmarks/links.
    """
    # Preserve query parameters and redirect to capacity tab
    query_string = request.META.get("QUERY_STRING", "")
    redirect_url = "/analytics/?tab=capacity"
    if query_string:
        redirect_url += f"&{query_string}"
    return redirect(redirect_url)


def analytics_dashboard(request: HttpRequest) -> HttpResponse:
    """Unified analytics dashboard with revenue, clients, capacity, and expenses.

    P-004: Consolidated analytics + practice_analysis into tab-based view.
    Combines financial trends (revenue, expenses, profit) with practice metrics
    (client classification, capacity utilization, trends).
    """
    # Extract filter parameters
    period = request.GET.get("period", "all")
    custom_start = request.GET.get("start_date")
    custom_end = request.GET.get("end_date")
    active_tab = request.GET.get("tab", "revenue")  # Default to revenue tab

    # Build analytics context using builder class (practice-scoped)
    builder = AnalyticsDashboardBuilder(request, period, custom_start, custom_end)
    context = builder.build_context()
    context["active_tab"] = active_tab

    # Reuse the dates already parsed by the builder for practice analysis
    start_date = builder.start_date
    end_date = builder.end_date

    # Run practice analysis if we have date range (for Clients/Capacity tabs)
    if start_date and end_date:
        analyzer = PracticeAnalyzer(start_date, end_date)
        analysis = analyzer.analyze_with_insights()
        trends = calculate_quarter_trends(end_date)

        context.update(
            {
                "practice_analysis": analysis,
                "practice_trends": trends,
                "analysis_start_date": start_date.isoformat(),
                "analysis_end_date": end_date.isoformat(),
            }
        )

    return render(request, "my_practice/analytics.html", context)


def revenue_report(request):
    """Detailed revenue report by payment year"""
    selected_year = get_year_from_request(request, "year", None)

    # Get available years from paid invoices (filtered by current practice)
    available_years = sorted(
        set(
            Invoice.objects.for_current_practice(request)
            .filter(status="paid")
            .exclude(paid_date__isnull=True)
            .values_list("paid_date__year", flat=True)
            .distinct()
        ),
        reverse=True,
    )

    context: dict[str, Any] = {
        "available_years": available_years,
        "selected_year": selected_year,
    }

    if selected_year:
        year = selected_year

        # Get all invoices paid in this year
        # Use centralized filter helper (M-PAT-02: Date Filter Patterns)
        invoices = (
            Invoice.objects.for_current_practice(request)
            .filter(
                RevenueCalculator.build_paid_date_filter(year),
                status="paid",
            )
            .select_related("client")  # Optimize client access (2026-01-30)
            .order_by("paid_date", "invoice_date", "invoice_number")
        )

        # Annotate invoices with year_diff flag
        invoice_list = []
        for inv in invoices:
            paid_year = inv.paid_date.year if inv.paid_date else inv.invoice_date.year
            invoice_year = inv.invoice_date.year
            inv.year_diff = paid_year != invoice_year
            invoice_list.append(inv)

        # Calculate summary statistics in one pass
        total = Decimal(0)
        same_year_total = Decimal(0)
        prev_year_total = Decimal(0)
        same_year_count = 0
        prev_year_count = 0
        for inv in invoice_list:
            total += inv.total
            if inv.year_diff:
                prev_year_total += inv.total
                prev_year_count += 1
            else:
                same_year_total += inv.total
                same_year_count += 1

        summary: dict[str, Any] = {
            "total": total,
            "count": len(invoice_list),
            "same_year_count": same_year_count,
            "same_year_total": same_year_total,
            "prev_year_count": prev_year_count,
            "prev_year_total": prev_year_total,
        }

        context.update(
            {
                "invoices": invoice_list,
                "summary": summary,
            }
        )

    return render(request, "my_practice/revenue_report.html", context)
