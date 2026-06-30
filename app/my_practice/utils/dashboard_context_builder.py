"""
Context assembler for the main dashboard view.
"""

from datetime import date

from django.db.models import Sum
from django.template.loader import render_to_string
from django.utils.safestring import SafeString, mark_safe

from ..models import Client, CompanyExpense, Invoice, TimeOff
from .action_queue_builder import ActionQueueBuilder
from .agenda_helpers import AgendaWidgetBuilder
from .dashboard_widgets import CapacityMonitoringWidgetBuilder
from .weekly_focus_widget import WeeklyFocusWidgetBuilder
from .practice_helpers import get_user_practices
from .revenue_helpers import RevenueCalculator


class DashboardContextAssembler:
    """
    Builds the full context dict for the main dashboard view.

    Usage:
        assembler = DashboardContextAssembler(request, today=date.today())
        context = assembler.build()
    """

    def __init__(self, request, today: date) -> None:
        self.request = request
        self.today = today
        self.practice = request.current_practice

    # ── Public API ────────────────────────────────────────────────────────────

    def build(self) -> dict:
        context: dict = {}
        context.update(self._build_statistics())
        context.update(self._build_timeoff())
        context.update(self._build_widgets())
        context.update(self._build_action_queue())
        context.update(self._build_multi_practice())
        return context

    def _build_statistics(self) -> dict:
        today = self.today
        current_year = today.year
        current_month = today.month
        practice = self.practice

        total_invoices = Invoice.objects.for_current_practice(self.request).count()
        total_revenue = RevenueCalculator.get_total_revenue(filters={"practice": practice})

        year_stats = RevenueCalculator.get_year_revenue(
            current_year, use_paid_date=True, practice=practice
        )
        month_stats_now = RevenueCalculator.get_month_revenue(
            current_year, current_month, practice=practice
        )
        status_stats = RevenueCalculator.get_status_breakdown(filters={"practice": practice})

        year_expenses = (
            CompanyExpense.objects.for_current_practice(self.request)
            .filter(date__year=current_year)
            .aggregate(total=Sum("amount"))["total"]
            or 0
        )

        recent_invoices = (
            Invoice.objects.for_current_practice(self.request)
            .select_related("client")
            .prefetch_related("items__service_type")
            .order_by("-invoice_date")[:10]
        )

        active_clients = (
            Client.objects.for_current_practice(self.request)
            .filter(invoices__isnull=False)
            .distinct()
            .count()
        )

        return {
            "total_invoices": total_invoices,
            "total_revenue": total_revenue,
            "year_revenue": year_stats["total"],
            "year_count": year_stats["count"],
            "year_expenses": year_expenses,
            "year_profit": year_stats["total"] - year_expenses,
            "month_revenue": month_stats_now["total"],
            "month_count": month_stats_now["count"],
            "status_stats": status_stats,
            "unpaid_value": status_stats["sent"]["total"] or 0,
            "unpaid_count": status_stats["sent"]["count"] or 0,
            "recent_invoices": recent_invoices,
            "active_clients": active_clients,
            "current_year": current_year,
            "current_month": today.strftime("%B"),
        }

    def _build_timeoff(self) -> dict:
        from ..utils.timeoff_helpers import calculate_timeoff_for_year

        today = self.today
        result = calculate_timeoff_for_year(today.year)
        return {
            "total_days_off": result["total_days"],
            "total_weeks_off": result["total_weeks"],
            "total_workdays_off": result["total_workdays"],
            "current_timeoff": TimeOff.objects.filter(
                start_date__lte=today, end_date__gte=today
            ).first(),
            "upcoming_timeoff": TimeOff.objects.filter(start_date__gt=today)
            .order_by("start_date")
            .first(),
        }

    def _build_widgets(self) -> dict:
        practice = self.practice
        today = self.today

        agenda_ctx = AgendaWidgetBuilder(practice, target_date=today).build_context()
        sc, tc, uc = (
            agenda_ctx["session_count"],
            agenda_ctx["task_count"],
            agenda_ctx["unscheduled_count"],
        )
        agenda_badge_parts = [
            f'<span class="stat-badge">{sc} Sitzung{"en" if sc != 1 else ""}</span>',
            f'<span class="stat-badge">{tc} Aufgabe{"n" if tc != 1 else ""}</span>',
        ]
        if uc > 0:
            agenda_badge_parts.append(f'<span class="stat-badge warning">{uc} ohne Uhrzeit</span>')

        cap_ctx = CapacityMonitoringWidgetBuilder(practice).build_context()
        wf_ctx = WeeklyFocusWidgetBuilder(practice).build_context()
        focus_count = wf_ctx["focus_count"]
        wf_session_count = wf_ctx["session_count"]
        wf_badge_parts = [f'<span class="stat-badge">{wf_session_count} Sitzungen</span>']
        if focus_count:
            wf_badge_parts.append(f'<span class="stat-badge">{focus_count} Fokus</span>')

        def _html(template: str, ctx: dict) -> SafeString:
            return mark_safe(render_to_string(template, ctx))

        return {
            "agenda_widget_html": _html(
                "includes/agenda_widget_content.html",
                {
                    "agenda_items": agenda_ctx["agenda_items"],
                    "target_date": agenda_ctx["target_date"],
                    "is_today": agenda_ctx["is_today"],
                },
            ),
            "agenda_badge_html": mark_safe("".join(agenda_badge_parts)),
            "capacity_widget_html": _html(
                "includes/capacity_monitoring_widget_content.html", cap_ctx
            ),
            "capacity_badge": (
                mark_safe('<span class="stat-badge warning">⚠️ Kapazität</span>')
                if cap_ctx.get("show_warning")
                else ""
            ),
            "capacity_show_widget": cap_ctx.get("show_widget", False),
            "weekly_focus_widget_html": _html("includes/weekly_focus_widget_content.html", wf_ctx),
            "weekly_focus_badge": mark_safe(" ".join(wf_badge_parts)),
        }

    def _build_action_queue(self) -> dict:
        return {"action_queue_items": ActionQueueBuilder(self.practice).build()}

    def _build_multi_practice(self) -> dict:
        request = self.request
        user_practices = get_user_practices(request.user) if request.user.is_authenticated else []
        practice_stats = []
        if len(user_practices) > 1:
            current_year = self.today.year
            practice_stats.extend(
                {
                    "practice": p,
                    "revenue": RevenueCalculator.get_total_revenue(
                        {"practice": p, "paid_date__year": current_year}
                    ),
                    "invoice_count": Invoice.objects.filter(
                        practice=p, invoice_date__year=current_year
                    ).count(),
                    "is_current": (p.id == self.practice.id if self.practice else False),
                }
                for p in user_practices
            )
        return {"user_practices": user_practices, "practice_stats": practice_stats}
