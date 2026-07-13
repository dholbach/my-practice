"""Builder for the client_detail view context."""

from datetime import date, timedelta
from itertools import chain

from dateutil.relativedelta import relativedelta

from ..models import ClientDocument, ClientNote, ClientProfile, ClientTag, Invoice, InvoiceItem
from ..models.clinical import (
    CASE_NOTES_TEMPLATE,
    INTAKE_NOTES_TEMPLATE,
    SESSION_LOG_TEMPLATE,
    MoodTag,
)
from ..models.session import Session
from .chart_helpers import aggregate_invoice_items_by_month, prepare_monthly_chart_data
from .calculations import count_sessions
from .questionnaire_content import list_available_questionnaires
from .revenue_helpers import RevenueCalculator
from .tag_helpers import sort_tags_by_category

_MONTHS_DE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def _fmt_month(d: date) -> str:
    return f"{_MONTHS_DE[d.month - 1]} {d.strftime('%y')}"


class ClientDetailContextBuilder:
    """Builds the full context dict for the client_detail view.

    Mirrors the pattern of AnalyticsDashboardBuilder — instantiate with the
    fetched client, call .build(), pass the result straight to render().
    """

    def __init__(self, client, request):
        self.client = client
        self.request = request
        self.today = date.today()
        self.invoices = client.invoices.all()
        # Built once; shared by _build_stats and _build_billing_context.
        self.all_items = [
            item
            for invoice in self.invoices
            for item in invoice.items.select_related("session").all()
        ]

    def build(self) -> dict:
        context = {"client": self.client, "invoices": self.invoices}
        context.update(self._build_stats())
        context.update(self._build_billing_context())
        context.update(self._build_clinical_context())
        return context

    # ── Stats ─────────────────────────────────────────────────────────────────

    def _build_stats(self) -> dict:
        revenue_stats = RevenueCalculator.get_client_revenue(self.client)

        non_cancelled = [
            item for item in self.all_items if not (item.session_id and item.session.cancelled)
        ]
        total_hours = count_sessions(self.all_items, exclude_cancellations=True)
        session_count = len(non_cancelled)
        total_minutes = sum(
            item.session.duration if item.session_id else 0 for item in non_cancelled
        )
        avg_duration = round(total_minutes / session_count) if session_count > 0 else 0

        finalized = [inv for inv in self.invoices if inv.status != "draft"]
        last_invoice_date = finalized[0].invoice_date if finalized else None

        items_with_session = [item for item in self.all_items if item.session_id]
        if items_with_session:
            session_dates = [item.session.session_date for item in items_with_session]
            first_session_date = min(session_dates)
            last_session_date = max(session_dates)
        else:
            first_session_date = last_session_date = None

        four_months_ago = self.today - relativedelta(months=4)
        is_recently_active = bool(
            self.client.active and last_session_date and last_session_date >= four_months_ago
        )
        activity_period = self._format_activity_period(
            first_session_date, last_session_date, is_recently_active
        )
        open_amount = sum(float(inv.total) for inv in self.invoices if inv.status == "sent")

        monthly_aggregation = aggregate_invoice_items_by_month(
            self.all_items, exclude_cancellations=True
        )
        monthly_data = prepare_monthly_chart_data(
            monthly_aggregation, label_format="short", value_key="hours", fill_gaps=True
        )
        for item in monthly_data:
            item["hours"] = round(item["hours"], 1)

        available_tags = ClientTag.objects.filter(is_system=False).exclude(clients=self.client)
        client_manual_tags = self.client.tags.filter(is_system=False)

        return {
            "stats": {
                "total_revenue": float(revenue_stats["total"]),
                "paid_count": revenue_stats["count"],
                "total_hours": total_hours,
                "session_count": session_count,
                "avg_duration": avg_duration,
                "last_invoice_date": last_invoice_date,
                "first_session_date": first_session_date,
                "last_session_date": last_session_date,
                "is_recently_active": is_recently_active,
                "activity_period": activity_period,
                "open_amount": open_amount,
            },
            "monthly_sessions": monthly_data,
            "available_tags": sort_tags_by_category(available_tags),
            "client_manual_tags": client_manual_tags,
        }

    @staticmethod
    def _format_activity_period(
        first: date | None, last: date | None, is_recently_active: bool
    ) -> str | None:
        if not first:
            return None
        start_str = _fmt_month(first)
        if is_recently_active:
            return f"seit {start_str}"
        if last:
            end_str = _fmt_month(last)
            return f"{start_str} – {end_str}" if end_str != start_str else start_str
        return start_str

    # ── Billing ───────────────────────────────────────────────────────────────

    def _build_billing_context(self) -> dict:
        sent_invoices = [inv for inv in self.invoices if inv.status == "sent"]
        if sent_invoices:
            oldest_days = (self.today - min(inv.invoice_date for inv in sent_invoices)).days
            if oldest_days > 30:
                reminder_urgency = "high"
            elif oldest_days >= 14:
                reminder_urgency = "medium"
            else:
                reminder_urgency = "low"
        else:
            reminder_urgency = None

        pending_sessions = self.client.pending_calendar_events.filter(
            status="pending",
            event_date__gte=self.today,
        ).order_by("event_date", "event_time")

        current_draft_invoice = self.client.invoices.filter(status="draft").first()

        billed_session_ids = set(
            InvoiceItem.objects.filter(invoice__client=self.client)
            .exclude(invoice__status=Invoice.Status.CANCELLED)
            .values_list("session_id", flat=True)
        )
        unbilled_qs = Session.objects.filter(
            client=self.client,
            cancelled=False,
            duration__gt=20,
            billable=True,
        ).exclude(pk__in=billed_session_ids)

        current_month_pending_count = self.client.pending_calendar_events.filter(
            status="pending",
            event_date__year=self.today.year,
            event_date__month=self.today.month,
        ).count()
        current_month_unbilled_count = unbilled_qs.filter(
            session_date__year=self.today.year,
            session_date__month=self.today.month,
        ).count()
        current_month_str = f"{self.today.year}-{self.today.month:02d}"

        return {
            "reminder_urgency": reminder_urgency,
            "pending_sessions": pending_sessions,
            "current_draft_invoice": current_draft_invoice,
            "current_month_pending_count": current_month_pending_count,
            "current_month_unbilled_count": current_month_unbilled_count,
            "current_month_str": current_month_str,
        }

    # ── Clinical ──────────────────────────────────────────────────────────────

    def _build_clinical_context(self) -> dict:
        from ..models import SessionLog

        profile, _ = ClientProfile.objects.get_or_create(client=self.client)

        # Last 5 session logs for Überblick tab (unencrypted metadata only)
        recent_session_logs = (
            SessionLog.objects.filter(session__client=self.client, session__cancelled=False)
            .select_related("session")
            .order_by("-session__session_date")[:5]
        )

        # Intake progress: 4 steps tracked as date fields on Client
        intake_steps = [
            ("Aufnahme", self.client.intake_sent_date),
            ("Vertrag", self.client.contract_signed_date),
            ("Anamnese", self.client.questionnaire_sent_date),
            ("Abschluss", self.client.onboarding_complete_date),
        ]
        intake_steps_done = sum(1 for _, d in intake_steps if d)

        sessions_qs = (
            self.client.sessions.filter(cancelled=False)
            .prefetch_related(
                "log",
                "invoice_items__invoice",
                "gebueh_leistungen__ziffer",
            )
            .order_by("-session_date")
        )

        no_log_needed_session_ids: set[int] = set(
            self.client.sessions.filter(cancelled=True).values_list("pk", flat=True)
        )

        recent_cutoff = self.today - timedelta(days=7)
        recent_sessions_needing_log = set(
            self.client.sessions.filter(
                log__isnull=True,
                session_date__gte=recent_cutoff,
                session_date__lte=self.today,
            )
            .exclude(pk__in=no_log_needed_session_ids)
            .values_list("pk", flat=True)
        )

        notes_qs = ClientNote.objects.filter(client=self.client).order_by(
            "-note_date", "-created_at"
        )
        log_entries = sorted(
            chain(
                [{"type": "session", "date": s.session_date, "obj": s} for s in sessions_qs],
                [{"type": "note", "date": n.note_date, "obj": n} for n in notes_qs],
            ),
            key=lambda e: e["date"],
            reverse=True,
        )

        gebueh_diagnostic_count = 0
        if self.client.needs_gebueh_invoice:
            from ..models.gebueh import Leistungserfassung

            gebueh_diagnostic_count = Leistungserfassung.objects.filter(
                session__client=self.client,
                ziffer__nummer__in=["1", "19.5", "19.6"],
            ).count()

        return {
            "profile": profile,
            "recent_session_logs": recent_session_logs,
            "intake_steps": intake_steps,
            "intake_steps_done": intake_steps_done,
            "log_entries": log_entries,
            "recent_sessions_needing_log": recent_sessions_needing_log,
            "no_log_needed_session_ids": no_log_needed_session_ids,
            "supervision_items": self.client.supervision_items.order_by("-created_at"),
            "session_type_choices": SessionLog.SessionType.choices,
            "mood_tag_choices": MoodTag.choices,
            "intake_notes_template": INTAKE_NOTES_TEMPLATE,
            "case_notes_template": CASE_NOTES_TEMPLATE,
            "session_log_template": SESSION_LOG_TEMPLATE,
            "documents": self.client.documents.order_by("-document_date", "-created_at"),
            "doc_type_choices": ClientDocument.DOC_TYPE_CHOICES,
            "gebueh_diagnostic_count": gebueh_diagnostic_count,
            "available_questionnaires": list_available_questionnaires(),
        }
