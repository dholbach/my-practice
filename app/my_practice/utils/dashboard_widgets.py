"""
Widget builders for dashboard - P-003 Phase 4 + P-012
Additional widgets: Session Import, Client Attention, Invoice Actions, Bank Import Reminder, Checklist
"""

from datetime import date, timedelta

from django.db.models import Max, QuerySet, Sum
from django.urls import reverse

from ..models import (
    BankTransaction,
    ChecklistItemPause,
    Client,
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


class ClientAttentionWidgetBuilder:
    """
    Builds context for Client Attention Widget.

    Shows:
    - Clients without next session scheduled
    - Clients with specific tags requiring attention
    - Follow-up recommendations

    Usage:
        builder = ClientAttentionWidgetBuilder(practice)
        context = builder.build_context()
    """

    def __init__(self, practice):
        self.practice = practice

    def _get_clients_without_next_session(self) -> QuerySet:
        """Get active clients who haven't had a non-cancelled session in 60+ days"""
        cutoff_date = date.today() - timedelta(days=60)

        recent_session_clients = (
            Session.objects.filter(
                client__practice=self.practice,
                session_date__gte=cutoff_date,
                cancelled=False,
            )
            .values_list("client_id", flat=True)
            .distinct()
        )

        # Exclude clients with recent sessions, filter only active clients
        return (
            Client.objects.filter(practice=self.practice, active=True)
            .exclude(id__in=recent_session_clients)
            .prefetch_related("tags")
        )

    def _get_tagged_clients(self) -> dict:
        """Get clients grouped by attention-requiring tags"""
        from ..models import ClientTag

        # Tags requiring attention - shown in dashboard widget
        attention_tags = [
            "follow-up",
            "pause",
            "ending",
            "missing-session-log",
        ]

        tagged_clients = {}
        for tag_name in attention_tags:
            try:
                tag = ClientTag.objects.get(name=tag_name)
                clients = Client.objects.filter(practice=self.practice, tags=tag).prefetch_related(
                    "tags"
                )
                if clients.exists():
                    tagged_clients[tag_name] = {
                        "tag": tag,
                        "clients": clients,
                        "count": clients.count(),
                    }
            except ClientTag.DoesNotExist:
                continue

        return tagged_clients

    def build_context(self) -> dict:
        """
        Build context for client attention widget.

        Returns:
            dict with:
                - no_recent_session_clients: QuerySet
                - no_recent_session_count: int
                - tagged_clients: dict {tag_name: {tag, clients, count}}
                - total_attention_count: int
        """
        no_recent_clients = self._get_clients_without_next_session()
        tagged_clients = self._get_tagged_clients()

        no_recent_count = no_recent_clients.count()
        tagged_count = sum(data["count"] for data in tagged_clients.values())

        return {
            "no_recent_session_clients": no_recent_clients[:5],  # Limit to 5
            "no_recent_session_count": no_recent_count,
            "tagged_clients": tagged_clients,
            "total_attention_count": no_recent_count + tagged_count,
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

    def _get_overdue_invoices(self) -> QuerySet:
        """Get invoices overdue (sent > 30 days ago, not paid)"""
        cutoff_date = date.today() - timedelta(days=30)
        return (
            Invoice.objects.filter(
                practice=self.practice,
                status="sent",
                invoice_date__lt=cutoff_date,
            )
            .select_related("client")
            .order_by("invoice_date")
        )

    def _get_draft_invoices(self) -> QuerySet:
        """Get draft invoices ready to send, annotated with last session date"""
        return (
            Invoice.objects.filter(practice=self.practice, status="draft")
            .select_related("client")
            .annotate(last_session_date=Max("items__session__session_date"))
            .order_by("last_session_date")  # Oldest sessions first
        )

    def build_context(self) -> dict:
        """
        Build context for invoice actions widget.

        Returns:
            dict with:
                - unpaid_invoices: QuerySet (limited to 5)
                - unpaid_count: int
                - unpaid_total: Decimal
                - overdue_invoices: QuerySet (limited to 5)
                - overdue_count: int
                - draft_invoices: QuerySet (limited to 5)
                - draft_count: int
        """
        unpaid = self._get_unpaid_invoices()
        overdue = self._get_overdue_invoices()
        drafts = self._get_draft_invoices()

        # Calculate totals
        unpaid_total = sum(inv.calculate_total() for inv in unpaid)

        return {
            "unpaid_invoices": unpaid[:5],
            "unpaid_count": unpaid.count(),
            "unpaid_total": unpaid_total,
            "overdue_invoices": overdue[:5],
            "overdue_count": overdue.count(),
            "draft_invoices": drafts[:5],
            "draft_count": drafts.count(),
        }


class BankImportReminderWidgetBuilder:
    """
    Builds context for Bank Import Reminder Widget (P-012).

    Shows warning if last bank statement import was >30 days ago.

    Usage:
        builder = BankImportReminderWidgetBuilder(practice)
        context = builder.build_context()
    """

    def __init__(self, practice):
        self.practice = practice

    def build_context(self) -> dict:
        """
        Build context for bank import reminder widget.

        Returns:
            dict with:
                - show_reminder: Boolean (True if >30 days since last import)
                - days_since_import: int or None
                - last_import_date: date or None
                - import_url: URL to bank import page
        """
        # Get last imported transaction
        last_transaction = (
            BankTransaction.objects.filter(practice=self.practice).order_by("-imported_at").first()
        )

        if not last_transaction:
            # No imports yet - show reminder
            return {
                "show_reminder": True,
                "days_since_import": None,
                "last_import_date": None,
                "import_url": reverse("bank_import"),
                "message": "Noch keine Kontoauszüge importiert",
            }

        # Calculate days since last import
        today = date.today()
        days_since = (today - last_transaction.imported_at.date()).days

        # Show reminder if >30 days
        show_reminder = days_since > 30

        return {
            "show_reminder": show_reminder,
            "days_since_import": days_since,
            "last_import_date": last_transaction.imported_at.date(),
            "import_url": reverse("bank_import"),
            "message": (f"Letzter Import vor {days_since} Tagen" if show_reminder else None),
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
        ("monthly", "Monatlicher Restore-Test"),
        ("weekly", "W\u00f6chentliche Sicherung"),
        ("quarterly", "MicroSD-Offsite-Backup (Karte A/B im Wechsel, alle 2 Wochen)"),
        ("annual", "J\u00e4hrliche Sicherheitsüberprüfung"),
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


class TaxQuarterWidgetBuilder:
    """
    Builds context for the Tax Quarter Widget (P-013 Phase 2).

    Shows the current quarter's revenue and whether a Steuervorauszahlung
    (tax prepayment withdrawal, category='tax') has already been recorded.
    Displays a warning badge if the quarter is more than halfway through
    and no prepayment has been entered yet.

    Usage:
        builder = TaxQuarterWidgetBuilder(practice)
        context = builder.build_context()
    """

    def __init__(self, practice):
        self.practice = practice

    @staticmethod
    def _quarter_of(d: date) -> tuple[int, date, date]:
        """Return (quarter_number, start, end) for the given date."""
        import calendar as cal

        q = (d.month - 1) // 3 + 1
        start_month = (q - 1) * 3 + 1
        end_month = start_month + 2
        start = date(d.year, start_month, 1)
        end = date(d.year, end_month, cal.monthrange(d.year, end_month)[1])
        return q, start, end

    def build_context(self) -> dict:
        """
        Build context for the tax quarter widget.

        Returns:
            dict with:
                - current_quarter: int (1-4)
                - quarter_revenue: Decimal
                - has_tax_payment: bool
                - show_warning: bool (quarter half over, no payment recorded)
                - quarter_overview_url: URL
                - add_payment_url: URL (pre-fills category=tax)
        """
        from ..models import CompanyWithdrawal, Invoice

        today = date.today()
        q, start, end = self._quarter_of(today)

        revenue = (
            Invoice.objects.filter(
                practice=self.practice,
                status="paid",
                paid_date__range=(start, end),
            ).aggregate(total=Sum("total"))["total"]
            or 0
        )

        has_tax_payment = CompanyWithdrawal.objects.filter(
            practice=self.practice,
            category="tax",
            date__range=(start, end),
        ).exists()

        days_in_quarter = (end - start).days + 1
        days_elapsed = (today - start).days
        show_warning = not has_tax_payment and days_elapsed >= days_in_quarter // 2

        return {
            "current_quarter": q,
            "quarter_revenue": revenue,
            "has_tax_payment": has_tax_payment,
            "show_warning": show_warning,
            "quarter_overview_url": reverse("tax_quarter_overview"),
            "add_payment_url": reverse("withdrawal_create") + "?category=tax",
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
        sessions = Session.objects.filter(
            client__practice=self.practice,
            session_date__year=year,
            session_date__month=month,
            cancelled=False,
        )
        hours = sum(s.duration / 60.0 / s.group_size for s in sessions)

        revenue = (
            Invoice.objects.filter(
                practice=self.practice,
                status="paid",
                paid_date__year=year,
                paid_date__month=month,
            ).aggregate(total=Sum("total"))["total"]
            or 0
        )

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
