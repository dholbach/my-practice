"""
Widget builders for dashboard - P-003 Phase 4 + P-012
Additional widgets: Session Import, Client Attention, Invoice Actions, Bank Import Reminder, Checklist
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Max, QuerySet
from django.urls import reverse
from django.utils.translation import gettext, ngettext, pgettext
from django.utils.translation import gettext_lazy as _

from ..models import (
    BankTransaction,
    ChecklistItemPause,
    Client,
    GoogleCalendarToken,
    Invoice,
    OperationalChecklistCompletion,
    Session,
)

# Tag labels for action-queue display — kept here alongside the tag logic
_TAG_LABELS: dict[str, object] = {
    "follow-up": _("Follow-up"),
    "pause": _("Pause"),
    "ending": _("Completion"),
    "missing-session-log": _("Log missing"),
}


def _fmt_eur(amount: Decimal) -> str:
    formatted = f"{float(amount):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} €"


def _join_truncated(items: list[str], total: int, sep: str = ", ", max_shown: int = 4) -> str:
    shown = [str(item) for item in items[:max_shown]]
    result = sep.join(shown)
    if total > len(shown):
        result += " …"
    return result


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

        tags_by_name = {tag.name: tag for tag in ClientTag.objects.filter(name__in=attention_tags)}
        clients_by_tag: dict[str, list[Client]] = {
            name: [] for name in attention_tags if name in tags_by_name
        }

        clients = (
            Client.objects.filter(practice=self.practice, tags__name__in=attention_tags)
            .prefetch_related("tags")
            .distinct()
        )
        for client in clients:
            for tag in client.tags.all():
                if tag.name in clients_by_tag:
                    clients_by_tag[tag.name].append(client)

        return {
            name: {
                "tag": tags_by_name[name],
                "clients": members,
                "count": len(members),
            }
            for name, members in clients_by_tag.items()
            if members
        }

    def get_missing_session_log_clients(self) -> QuerySet:
        """
        Clients currently tagged "missing-session-log" (kept in sync by the
        update_client_tags management command). Public so the P-050 Focus
        Queue task sync can materialize a Task per client without
        re-deriving the underlying condition.
        """
        return Client.objects.filter(
            practice=self.practice, tags__name="missing-session-log"
        ).distinct()

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

    def get_action_items(self, today: date | None = None) -> list[dict]:
        """Return ActionQueueItem-shaped dicts for tagged and inactive clients."""
        today = today or date.today()
        items: list[dict] = []

        tagged_clients = self._get_tagged_clients()

        items.extend(
            {
                "priority": 2,
                "category": "CLIENT",
                "category_label": gettext("Client"),
                "summary": f"{client.client_code} · {_TAG_LABELS.get(tag_name, tag_name)}",
                "sub_text": "",
                "action_url": reverse("client_detail", kwargs={"pk": client.pk}),
                "action_label": gettext("Open"),
                "_sort_key": client.client_code,
            }
            for tag_name, data in tagged_clients.items()
            for client in data["clients"]
        )

        tagged_ids = {c.pk for data in tagged_clients.values() for c in data["clients"]}
        inactive = [
            c for c in self._get_clients_without_next_session()[:5] if c.pk not in tagged_ids
        ]

        if inactive:
            client_ids = [c.pk for c in inactive]
            last_sessions: dict = dict(
                Session.objects.filter(client_id__in=client_ids, cancelled=False)
                .values("client_id")
                .annotate(last=Max("session_date"))
                .values_list("client_id", "last")
            )
            for client in inactive:
                last_date = last_sessions.get(client.pk)
                if last_date:
                    days = (today - last_date).days
                    summary = f"{client.client_code} · " + gettext("no session for %(days)s d") % {
                        "days": days
                    }
                    sub = gettext("last %(date)s") % {"date": last_date.strftime("%d.%m.%Y")}
                    sort_key = f"inactive_{999 - days:04d}"
                else:
                    summary = f"{client.client_code} · " + gettext("no session yet")
                    sub = ""
                    sort_key = "inactive_9999"
                items.append(
                    {
                        "priority": 2,
                        "category": "CLIENT",
                        "category_label": gettext("Client"),
                        "summary": summary,
                        "sub_text": sub,
                        "action_url": reverse("client_detail", kwargs={"pk": client.pk}),
                        "action_label": gettext("Contact"),
                        "_sort_key": sort_key,
                    }
                )

        return items


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

    def get_action_items(self, today: date | None = None) -> list[dict]:
        """Return ActionQueueItem-shaped dicts for overdue and draft invoices."""
        today = today or date.today()
        items: list[dict] = []

        overdue = self.get_overdue_invoices(today)

        n_overdue = len(overdue)
        if n_overdue > 0:
            total = sum(inv.calculate_total() for inv in overdue)
            codes = _join_truncated(
                list(dict.fromkeys(inv.client.client_code for inv in overdue)),
                n_overdue,
            )
            oldest_age = max((today - inv.invoice_date).days for inv in overdue)
            items.append(
                {
                    "priority": 1,
                    "category": "INVOICE",
                    "category_label": pgettext("action category", "Invoice"),
                    "summary": gettext("%(n)s overdue · %(total)s")
                    % {"n": n_overdue, "total": _fmt_eur(total)},
                    "sub_text": gettext("%(codes)s · >%(days)s d")
                    % {"codes": codes, "days": oldest_age},
                    "action_url": reverse("invoice_list") + "?status=sent",
                    "action_label": gettext("Chase"),
                    "_sort_key": "0_overdue",
                }
            )

        drafts = list(self.get_draft_invoices())
        n_drafts = len(drafts)
        if n_drafts > 0:
            nums = _join_truncated([inv.invoice_number for inv in drafts], n_drafts, sep=" · ")
            label = ngettext("invoice ready", "invoices ready", n_drafts)
            items.append(
                {
                    "priority": 2,
                    "category": "DRAFT",
                    "category_label": gettext("Draft"),
                    "summary": gettext("%(n)s %(label)s to send") % {"n": n_drafts, "label": label},
                    "sub_text": nums,
                    "action_url": reverse("invoice_list") + "?status=draft",
                    "action_label": pgettext("action label", "Complete"),
                    "_sort_key": "1_drafts",
                }
            )

        return items


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
            BankTransaction.objects.for_practice(self.practice).order_by("-imported_at").first()
        )

        if not last_transaction:
            # No imports yet - show reminder
            return {
                "show_reminder": True,
                "days_since_import": None,
                "last_import_date": None,
                "import_url": reverse("bank_import"),
                "message": gettext("No bank statements imported yet"),
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
            "message": (
                gettext("Last import %(days)s days ago") % {"days": days_since}
                if show_reminder
                else None
            ),
        }

    def get_action_items(self, today: date | None = None) -> list[dict]:
        """Return an ActionQueueItem-shaped dict if a bank import reminder is due."""
        ctx = self.build_context()
        if not ctx["show_reminder"]:
            return []
        days = ctx["days_since_import"]
        summary = (
            gettext("Last bank import %(days)s days ago") % {"days": days}
            if days is not None
            else gettext("No bank statements imported yet")
        )
        return [
            {
                "priority": 3,
                "category": "OPS",
                "category_label": pgettext("action category", "Operations"),
                "summary": summary,
                "sub_text": "",
                "action_url": ctx["import_url"],
                "action_label": gettext("Import"),
                "_sort_key": "",
            }
        ]


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

    def get_action_items(self, today: date | None = None) -> list[dict]:
        """Return an ActionQueueItem-shaped dict if any checklists are pending."""
        ctx = self.build_context()
        entries = ctx["pending_checklists"]
        if not entries:
            return []
        n = len(entries)
        label = ngettext("checklist due", "checklists due", n)
        sub = _join_truncated([e["label"] for e in entries], n, sep=" · ", max_shown=3)
        return [
            {
                "priority": 2,
                "category": "OPS",
                "category_label": pgettext("action category", "Operations"),
                "summary": gettext("%(n)s %(label)s") % {"n": n, "label": label},
                "sub_text": sub,
                "action_url": reverse("checklist", kwargs={"checklist_type": entries[0]["type"]}),
                "action_label": gettext("View"),
                "_sort_key": str(entries[0]["period_start"]),
            }
        ]


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
        from ..models import CompanyWithdrawal
        from .date_helpers import DateRangeHelper
        from .revenue_helpers import RevenueCalculator

        today = date.today()
        q, start, end = DateRangeHelper.get_quarter_for_date(today)

        # Same paid-date rule (with invoice_date fallback) as the tax views
        revenue = RevenueCalculator.get_paid_revenue_for_range(start, end, practice=self.practice)

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

    def get_action_items(self, today: date | None = None) -> list[dict]:
        """Return an ActionQueueItem-shaped dict if a tax prepayment warning is active."""
        ctx = self.build_context()
        if not ctx["show_warning"]:
            return []
        revenue = ctx["quarter_revenue"]
        current_year = (today or date.today()).year
        return [
            {
                "priority": 1,
                "category": "TAX",
                "category_label": pgettext("action category", "Tax"),
                "summary": gettext("Q%(q)s %(year)s · prepayment missing")
                % {"q": ctx["current_quarter"], "year": current_year},
                "sub_text": gettext("Revenue: %(amount)s") % {"amount": _fmt_eur(revenue)},
                "action_url": ctx["add_payment_url"],
                "action_label": gettext("Record"),
                "_sort_key": "0_tax",
            }
        ]


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
