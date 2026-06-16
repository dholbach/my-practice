"""
Context assembler for the main dashboard view.
"""

from datetime import date
from typing import cast

from django.db.models import Sum
from django.template.loader import render_to_string
from django.utils.safestring import SafeString, mark_safe

from ..models import Client, CompanyExpense, Invoice, Session, TimeOff
from .agenda_helpers import AgendaWidgetBuilder
from .chart_helpers import format_month_key, format_month_label
from .dashboard_widgets import (
    BankImportReminderWidgetBuilder,
    CapacityMonitoringWidgetBuilder,
    ChecklistWidgetBuilder,
    ClientAttentionWidgetBuilder,
    InvoiceActionsWidgetBuilder,
    TaxQuarterWidgetBuilder,
)
from .weekly_focus_widget import WeeklyFocusWidgetBuilder
from .date_helpers import DateRangeHelper
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
        self._params = self._parse_params()

    # ── Public API ────────────────────────────────────────────────────────────

    def build(self) -> dict:
        context: dict = {}
        context.update(self._params)
        context.update(self._build_statistics())
        heatmap_ctx = self._build_heatmap()
        context.update(heatmap_ctx)
        context.update(self._build_timeoff())
        context.update(self._build_widgets())
        context.update(self._build_multi_practice())
        return context

    # ── Private builders ──────────────────────────────────────────────────────

    def _parse_params(self) -> dict:
        request = self.request
        try:
            months_to_show = int(request.GET.get("months", 12))
        except ValueError, TypeError:
            months_to_show = 12

        try:
            offset_str = request.GET.get("offset", "0").replace(",", "")
            start_offset = int(float(offset_str))
        except ValueError, TypeError:
            start_offset = 0

        heatmap_sort = (
            request.GET.get("sort", "total")
            if request.GET.get("sort") in ("total", "recent")
            else "total"
        )
        return {
            "months_to_show": months_to_show,
            "start_offset": start_offset,
            "heatmap_sort": heatmap_sort,
            "next_offset": start_offset - months_to_show,
        }

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

        monthly_data = self._build_monthly_trend(current_year, current_month)

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
            "monthly_data": monthly_data,
            "max_monthly_revenue": (
                max(float(cast(float, m["revenue"])) for m in monthly_data) if monthly_data else 0.0
            ),
            "current_year": current_year,
            "current_month": today.strftime("%B"),
        }

    def _build_monthly_trend(self, current_year: int, current_month: int) -> list[dict]:
        monthly_data = []
        cursor = DateRangeHelper.add_months(date(current_year, current_month, 1), -11)
        for _ in range(12):
            stats = RevenueCalculator.get_month_revenue(
                cursor.year, cursor.month, practice=self.practice
            )
            month_key = format_month_key(cursor)
            monthly_data.append(
                {"month": format_month_label(month_key, "short"), "revenue": float(stats["total"])}
            )
            cursor = DateRangeHelper.add_months(cursor, 1)
        return monthly_data

    def _build_heatmap(self) -> dict:
        from ..utils.heatmap_utils import get_heatmap_data

        params = self._params
        result = get_heatmap_data(
            self.today.year,
            self.today.month,
            params["months_to_show"],
            params["start_offset"],
            practice=self.practice,
            sort=params["heatmap_sort"],
        )
        range_start = result["range_start_date"]
        range_end = result["range_end_date_full"]
        start_offset = params["start_offset"]

        return {
            "heatmap_data": result["heatmap_data"],
            "active_clients_with_totals": result["active_clients_with_totals"],
            "can_go_back": Session.objects.filter(
                client__practice=self.practice,
                session_date__lt=range_start,
            ).exists(),
            "can_go_forward": (
                start_offset > 0
                or Session.objects.filter(
                    client__practice=self.practice,
                    session_date__gt=range_end,
                ).exists()
            ),
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

        ca_ctx = ClientAttentionWidgetBuilder(practice).build_context()
        ia_ctx = InvoiceActionsWidgetBuilder(practice).build_context()
        invoice_badge_parts = []
        if ia_ctx["unpaid_count"] > 0:
            invoice_badge_parts.append(
                f'<span class="stat-badge">{ia_ctx["unpaid_count"]} unbezahlt</span>'
            )
        if ia_ctx["overdue_count"] > 0:
            invoice_badge_parts.append(
                f'<span class="stat-badge warning">{ia_ctx["overdue_count"]} überfällig</span>'
            )
        if ia_ctx["draft_count"] > 0:
            invoice_badge_parts.append(
                f'<span class="stat-badge">{ia_ctx["draft_count"]} Entwürfe</span>'
            )

        bi_ctx = BankImportReminderWidgetBuilder(practice).build_context()
        cl_ctx = ChecklistWidgetBuilder().build_context()
        tq_ctx = TaxQuarterWidgetBuilder(practice).build_context()
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
            "client_attention_widget_html": _html(
                "includes/client_attention_widget_content.html", ca_ctx
            ),
            "client_attention_badge": mark_safe(
                f'<span class="stat-badge">{ca_ctx["total_attention_count"]} Klienten</span>'
            ),
            "invoice_actions_widget_html": _html(
                "includes/invoice_actions_widget_content.html", ia_ctx
            ),
            "invoice_actions_badge": mark_safe("".join(invoice_badge_parts))
            if invoice_badge_parts
            else "",
            "bank_import_widget_html": _html("includes/bank_import_widget_content.html", bi_ctx),
            "bank_import_badge": (
                mark_safe(
                    '<span class="stat-badge warning">'
                    + (
                        f"{bi_ctx['days_since_import']} Tage"
                        if bi_ctx["days_since_import"] is not None
                        else "Kein Import"
                    )
                    + "</span>"
                )
                if bi_ctx["show_reminder"]
                else ""
            ),
            "bank_import_show_reminder": bi_ctx["show_reminder"],
            "checklist_widget_html": _html("includes/checklist_widget_content.html", cl_ctx),
            "checklist_badge": (
                mark_safe(
                    f'<span class="stat-badge warning">{cl_ctx["pending_count"]} fällig</span>'
                )
                if cl_ctx["show_widget"]
                else mark_safe('<span class="stat-badge">✅ Erledigt</span>')
            ),
            "checklist_show_widget": cl_ctx["show_widget"],
            "tax_quarter_widget_html": _html("includes/tax_quarter_widget_content.html", tq_ctx),
            "tax_quarter_badge": (
                mark_safe('<span class="stat-badge warning">⚠️ Vorauszahlung?</span>')
                if tq_ctx["show_warning"]
                else ""
            ),
            "tax_quarter_show_warning": tq_ctx["show_warning"],
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
