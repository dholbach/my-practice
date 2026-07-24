"""
Widget builders for dashboard - P-003 Phase 4 + P-012
Additional widgets: Session Import, Invoice Actions, Checklist
"""

from datetime import date, timedelta

from django.db.models import Max, QuerySet
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from ..models import (
    ChecklistItemPause,
    GoogleCalendarToken,
    Invoice,
    OperationalChecklistCompletion,
    Session,
)


class SessionImportWidgetBuilder:
    """
    Builds context for Session Import Widget.

    Shows:
    - Google Calendar connection status
    - Badge with new events count (if available)
    - Quick import link

    Usage:
        builder = SessionImportWidgetBuilder(practice)
        context = builder.build_context()
    """

    def __init__(self, practice):
        self.practice = practice

    def build_context(self) -> dict:
        """
        Build context for session import widget.

        Returns:
            dict with:
                - has_calendar_token: Boolean
                - token_expired: Boolean
                - estimated_events_count: Approximate count (last 30 days)
                - connect_url: URL to connect calendar
                - import_url: URL to import page
                - is_connected: Overall connection status
        """
        # Check for active calendar token
        token = (
            GoogleCalendarToken.objects.filter(practice=self.practice, is_active=True)
            .order_by("-created_at")
            .first()
        )

        has_token = token is not None
        token_expired = token.is_expired if token else False
        is_connected = has_token and not token_expired

        # Estimate events count (would require API call, so we'll show generic message)
        # In production, could cache this value or make async API call
        estimated_events_count = None  # Could be populated with cached value

        return {
            "has_calendar_token": has_token,
            "token_expired": token_expired,
            "is_connected": is_connected,
            "estimated_events_count": estimated_events_count,
            "connect_url": reverse("calendar_authorize"),
            "import_url": reverse("calendar_import"),
        }


class InvoiceActionsWidgetBuilder:
    """
    Builds context for Invoice Actions Widget.

    Shows:
    - Unpaid invoices (sent but not paid)
    - Overdue invoices
    - Draft invoices ready to send
    - Quick action buttons

    Usage:
        builder = InvoiceActionsWidgetBuilder(practice)
        context = builder.build_context()
    """

    def __init__(self, practice):
        self.practice = practice

    def _get_unpaid_invoices(self) -> QuerySet:
        """Get sent but unpaid invoices (includes overdue), sorted by oldest first"""
        return (
            Invoice.objects.filter(practice=self.practice, status="sent")
            .select_related("client")
            .order_by("invoice_date")  # Oldest first to prioritize overdue
        )

    def get_draft_invoices(self) -> QuerySet:
        """
        Get draft invoices ready to send, annotated with last session date.

        Public: also the detection logic for the P-050 Focus Queue's
        invoice_unsent materialized task.
        """
        return (
            Invoice.objects.filter(practice=self.practice, status="draft")
            .select_related("client")
            .annotate(last_session_date=Max("items__session__session_date"))
            .order_by("last_session_date")  # Oldest sessions first
        )

    def get_overdue_invoices(self, today: date | None = None) -> list[Invoice]:
        """
        Get sent invoices overdue by more than 30 days.

        Public: also the detection logic for the P-050 Focus Queue's
        invoice_unpaid materialized task.
        """
        today = today or date.today()
        cutoff_date = today - timedelta(days=30)
        return [inv for inv in self._get_unpaid_invoices() if inv.invoice_date < cutoff_date]

    def build_context(self) -> dict:
        """
        Build context for invoice actions widget.

        Returns:
            dict with:
                - unpaid_invoices: list (limited to 5)
                - unpaid_count: int
                - unpaid_total: Decimal
                - overdue_invoices: list (limited to 5)
                - overdue_count: int
                - draft_invoices: list (limited to 5)
                - draft_count: int
        """
        # Evaluate each queryset once; overdue is a subset of unpaid, so it is
        # derived in Python instead of hitting the DB again
        unpaid = list(self._get_unpaid_invoices())
        overdue = self.get_overdue_invoices()
        drafts = list(self.get_draft_invoices())

        unpaid_total = sum(inv.calculate_total() for inv in unpaid)
        overdue_total = sum(inv.calculate_total() for inv in overdue)

        return {
            "unpaid_invoices": unpaid[:5],
            "unpaid_count": len(unpaid),
            "unpaid_total": unpaid_total,
            "overdue_invoices": overdue[:5],
            "overdue_count": len(overdue),
            "overdue_total": overdue_total,
            "draft_invoices": drafts[:5],
            "draft_count": len(drafts),
        }


class ChecklistWidgetBuilder:
    """
    Builds context for the Operational Checklist Widget (P-012).

    Shows pending checklists for the current period of each type.
    Priority order: monthly > weekly > quarterly > annual.

    Usage:
        builder = ChecklistWidgetBuilder()
        context = builder.build_context()
    """

    # Ordered by display priority
    CHECKLIST_CADENCES = [
        ("monthly", _("Monthly restore test")),
        ("weekly", _("Weekly backup")),
        ("quarterly", _("MicroSD offsite backup (card A/B alternating, every 2 weeks)")),
        ("annual", _("Annual security review")),
    ]

    def _get_period_start(self, checklist_type: str) -> date:
        """Calculate the first day of the current period for a checklist type."""
        today = date.today()
        if checklist_type == "weekly":
            return today - timedelta(days=today.weekday())  # Monday
        elif checklist_type == "monthly":
            return date(today.year, today.month, 1)
        elif checklist_type == "quarterly":
            quarter_start_month = ((today.month - 1) // 3) * 3 + 1
            return date(today.year, quarter_start_month, 1)
        else:  # annual
            return date(today.year, 1, 1)

    def build_context(self) -> dict:
        """
        Build context for checklist widget.

        A checklist is pending only if it has at least one non-paused item.
        Checklists with all items actively paused are not shown.

        Returns:
            dict with:
                - pending_checklists: list of dicts with type, label, period_start
                - pending_count: int
                - show_widget: bool (True if any pending)
        """
        # Deferred import to avoid circular dependency (views -> utils)
        from ..views.operational_views import CHECKLIST_ITEMS

        pending = []
        for ct, label in self.CHECKLIST_CADENCES:
            period_start = self._get_period_start(ct)
            completed = OperationalChecklistCompletion.objects.filter(
                checklist_type=ct,
                year_month=period_start,
                completed_at__isnull=False,
            ).exists()
            if completed:
                continue

            # Check if every item for this type is actively paused
            all_item_ids = {item["id"] for item in CHECKLIST_ITEMS.get(ct, [])}
            actively_paused_ids = {
                p.item_id
                for p in ChecklistItemPause.objects.filter(checklist_type=ct)
                if p.is_active
            }
            if all_item_ids and all_item_ids <= actively_paused_ids:
                continue  # All items paused — nothing actionable

            pending.append(
                {
                    "type": ct,
                    "label": label,
                    "period_start": period_start,
                }
            )

        return {
            "pending_checklists": pending,
            "pending_count": len(pending),
            "show_widget": len(pending) > 0,
        }


class PendingCalendarWidgetBuilder:
    """
    Builds context for the Pending Calendar Events Widget (P-013).

    Shows the count of calendar events waiting for approval and a link
    to the approval queue. Only shown when matchable pending events exist.

    Usage:
        builder = PendingCalendarWidgetBuilder(practice)
        context = builder.build_context()
    """

    def __init__(self, practice):
        self.practice = practice

    def build_context(self) -> dict:
        """
        Build context for pending calendar events widget.

        Returns:
            dict with:
                - pending_count: int
                - show_widget: bool
                - approval_url: URL to the approval queue
        """
        from ..models import PendingCalendarEvent

        pending_count = PendingCalendarEvent.objects.filter(
            practice=self.practice,
            status=PendingCalendarEvent.Status.PENDING,
            matched_client__isnull=False,
        ).count()

        return {
            "pending_count": pending_count,
            "show_widget": pending_count > 0,
            "approval_url": reverse("calendar_approval_queue"),
        }


class CapacityMonitoringWidgetBuilder:
    """
    Builds context for Capacity Monitoring Widget (P-013 Phase 3).

    Shows current month's session hours vs target and paid revenue vs target.
    Displays a 3-month trend. Shows warning badges when below 80 % of target.
    The widget is hidden when neither target is configured on the Practice.
    """

    def __init__(self, practice):
        self.practice = practice

    def _get_month_stats(self, year: int, month: int) -> dict:
        """Return session hours and paid revenue for the given calendar month."""
        from .calculations import count_session_hours
        from .revenue_helpers import RevenueCalculator

        sessions = Session.objects.filter(
            client__practice=self.practice,
            session_date__year=year,
            session_date__month=month,
            cancelled=False,
        )
        hours = count_session_hours(sessions)

        revenue = RevenueCalculator.get_month_revenue(
            year, month, use_paid_date=True, practice=self.practice
        )["total"]

        return {"hours": round(hours, 1), "revenue": float(revenue)}

    def build_context(self) -> dict:
        """Build template context for the capacity monitoring widget."""
        if self.practice is None:
            return {"show_widget": False}

        has_targets = (
            self.practice.monthly_target_hours is not None
            or self.practice.monthly_target_revenue is not None
        )
        if not has_targets:
            return {"show_widget": False}

        today = date.today()

        # Build stats for current month and 2 previous months (oldest → newest)
        months = []
        for offset in range(2, -1, -1):
            month = today.month - offset
            year = today.year
            while month <= 0:
                month += 12
                year -= 1
            stats = self._get_month_stats(year, month)
            months.append(
                {
                    "year": year,
                    "month": month,
                    "label": f"{month:02d}/{year}",
                    **stats,
                }
            )

        current = months[-1]
        target_hours = (
            float(self.practice.monthly_target_hours)
            if self.practice.monthly_target_hours
            else None
        )
        target_revenue = (
            float(self.practice.monthly_target_revenue)
            if self.practice.monthly_target_revenue
            else None
        )

        hours_pct = round(current["hours"] / target_hours * 100) if target_hours else None
        revenue_pct = round(current["revenue"] / target_revenue * 100) if target_revenue else None

        warn_hours = bool(target_hours and current["hours"] < target_hours * 0.8)
        warn_revenue = bool(target_revenue and current["revenue"] < target_revenue * 0.8)

        return {
            "show_widget": True,
            "months": months,
            "current_hours": current["hours"],
            "current_revenue": current["revenue"],
            "target_hours": target_hours,
            "target_revenue": target_revenue,
            "hours_pct": hours_pct,
            "revenue_pct": revenue_pct,
            "warn_hours": warn_hours,
            "warn_revenue": warn_revenue,
            "show_warning": warn_hours or warn_revenue,
        }
