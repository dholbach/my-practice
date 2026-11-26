"""Builder for the client_detail view context."""

from datetime import date, timedelta
from decimal import Decimal
from functools import cached_property
from itertools import chain

from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.utils.translation import gettext as _

from ..models import (
    ClientDocument,
    ClientNote,
    ClientProfile,
    ClientTag,
    Invoice,
    InvoiceItem,
    SupervisionItem,
)
from ..models.case_sheet import ROWS_BY_KIND, ClinicalFact
from ..models.clinical import MoodTag
from ..models.session import Session
from .case_sheet import build_case_sheet, working_diagnosis
from .chart_helpers import (
    MONTH_ABBREVIATIONS,
    aggregate_invoice_items_by_month,
    prepare_monthly_chart_data,
)
from .for_next_time import build_for_next_time
from .questionnaire_content import list_available_questionnaires
from .revenue_helpers import RevenueCalculator
from .tag_helpers import sort_tags_by_category


def _fmt_month(d: date) -> str:
    return f"{MONTH_ABBREVIATIONS[d.month - 1]} {d.strftime('%y')}"


def _has_note(session) -> bool:
    """Whether the session's log has a note, a reflection or ideas (what the timeline folds)."""
    log = getattr(session, "log", None)  # no log: RelatedObjectDoesNotExist, an AttributeError
    return bool(log and (log.content or log.therapist_reflection or log.next_session_ideas))


class ClientDetailContextBuilder:
    """Builds the full context dict for the client_detail view.

    Mirrors the pattern of AnalyticsDashboardBuilder — instantiate with the
    fetched client, call .build(), pass the result straight to render().
    """

    def __init__(self, client, request):
        self.client = client
        self.request = request
        self.today = timezone.localdate()
        # client_detail() (client_views.py) prefetches invoices__items with
        # session/service_type already select_related, so .all() below reads
        # from that cache instead of issuing one query per invoice.
        self.invoices = client.invoices.all()
        # Built once; shared by _build_stats and _build_billing_context.
        self.all_items = [item for invoice in self.invoices for item in invoice.items.all()]

    def build(self) -> dict:
        context = {"client": self.client, "invoices": self.invoices}
        context.update(self._build_stats())
        context.update(self._build_billing_context())
        context.update(self._build_clinical_context())
        return context

    # ── Stats ─────────────────────────────────────────────────────────────────

    def _build_stats(self) -> dict:
        revenue_stats = RevenueCalculator.get_client_revenue(self.client)
        total_hours, session_count, avg_duration = self._session_stats()
        first_session_date, last_session_date, is_recently_active = self._activity_dates()
        activity_period = self._format_activity_period(
            first_session_date, last_session_date, is_recently_active
        )
        available_tags = ClientTag.objects.filter(is_system=False).exclude(clients=self.client)

        return {
            "stats": {
                "total_revenue": revenue_stats["total"],
                "paid_count": revenue_stats["count"],
                "total_hours": total_hours,
                "session_count": session_count,
                "avg_duration": avg_duration,
                "last_invoice_date": self._last_invoice_date(),
                "first_session_date": first_session_date,
                "last_session_date": last_session_date,
                "is_recently_active": is_recently_active,
                "activity_period": activity_period,
                "open_amount": self._open_amount(),
            },
            "monthly_sessions": self._monthly_chart_data(),
            "available_tags": sort_tags_by_category(available_tags),
        }

    @cached_property
    def _held_sessions(self) -> list[tuple[date, int]]:
        """``(date, minutes)`` of every session held: not cancelled, and not after today.

        Cancelled sessions did not take place and future ones have not yet. Read from the
        sessions, not from the invoices, so a session that is not invoiced yet counts: the
        invoice-based figures lagged behind by up to a billing cycle. (The per-month chart in
        the admin mode stays invoice-based: it is about what was billed.)
        """
        return list(
            self.client.sessions.filter(cancelled=False, session_date__lte=self.today).values_list(
                "session_date", "duration"
            )
        )

    def _session_stats(self) -> tuple[float, int, int]:
        """Hours, number and average length (minutes) of the sessions held."""
        minutes = [duration for _day, duration in self._held_sessions]
        total_minutes = sum(minutes)
        session_count = len(minutes)
        avg_duration = round(total_minutes / session_count) if session_count else 0
        return total_minutes / 60, session_count, avg_duration

    def _digest_context(self) -> dict | None:
        """The "anything for the case sheet?" card for ``?digest=<session pk>``, if it names a session.

        Shows the session and the lines already added from it, so several can be added one
        after the other. A pk that is not a session of this client shows no card.
        """
        raw = self.request.GET.get("digest", "")
        session = self.client.sessions.filter(pk=int(raw)).first() if raw.isdigit() else None
        if session is None:
            return None
        added = []
        for fact in ClinicalFact.objects.filter(client=self.client, source_session=session):
            row = ROWS_BY_KIND.get(fact.kind)
            cell = next((c.label for c in row.cells if c.key == fact.sub), "") if row else ""
            added.append(
                {"row": row.label if row else fact.kind, "cell": cell, "content": fact.content}
            )
        return {"session": session, "added": added}

    def _last_invoice_date(self) -> date | None:
        finalized = [inv for inv in self.invoices if inv.status != Invoice.Status.DRAFT]
        return finalized[0].invoice_date if finalized else None

    def _activity_dates(self) -> tuple[date | None, date | None, bool]:
        """First and last session held, and whether the client is recently active."""
        days = [day for day, _minutes in self._held_sessions]
        first_session_date, last_session_date = (min(days), max(days)) if days else (None, None)

        four_months_ago = self.today - relativedelta(months=4)
        is_recently_active = bool(
            self.client.active and last_session_date and last_session_date >= four_months_ago
        )
        return first_session_date, last_session_date, is_recently_active

    def _open_amount(self) -> Decimal:
        return sum(
            (inv.total for inv in self.invoices if inv.status == Invoice.Status.SENT), Decimal("0")
        )

    def _monthly_chart_data(self) -> list[dict]:
        monthly_aggregation = aggregate_invoice_items_by_month(
            self.all_items, exclude_cancellations=True
        )
        monthly_data = prepare_monthly_chart_data(
            monthly_aggregation, label_format="short", value_key="hours", fill_gaps=True
        )
        for item in monthly_data:
            item["hours"] = round(item["hours"], 1)
        return monthly_data

    @staticmethod
    def _format_activity_period(
        first: date | None, last: date | None, is_recently_active: bool
    ) -> str | None:
        if not first:
            return None
        start_str = _fmt_month(first)
        if is_recently_active:
            return _("since %(start)s") % {"start": start_str}
        if last:
            end_str = _fmt_month(last)
            return f"{start_str} – {end_str}" if end_str != start_str else start_str
        return start_str

    # ── Billing ───────────────────────────────────────────────────────────────

    def _build_billing_context(self) -> dict:
        sent_invoices = [inv for inv in self.invoices if inv.status == Invoice.Status.SENT]
        if sent_invoices:
            oldest_invoice_date = min(inv.invoice_date for inv in sent_invoices)
            oldest_days = Invoice.days_overdue(oldest_invoice_date, self.today)
            practice = self.client.practice
            if oldest_days > practice.overdue_after_days:
                reminder_urgency = "high"
            elif oldest_days >= practice.payment_terms_days:
                reminder_urgency = "medium"
            else:
                reminder_urgency = "low"
        else:
            reminder_urgency = None

        pending_sessions = self.client.pending_calendar_events.filter(
            status="pending",
            event_date__gte=self.today,
        ).order_by("event_date", "event_time")

        current_draft_invoice = self.client.invoices.filter(status=Invoice.Status.DRAFT).first()

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

        # The old free-text notes, shown read-only below the case sheet until they are retired.
        profile = ClientProfile.objects.filter(client=self.client).first()

        # Intake progress: 4 steps tracked as date fields on Client (the overview shows
        # "N of 4" while the intake process is open; the checklist itself is in the admin mode).
        intake_steps_done = sum(
            1
            for step_date in (
                self.client.intake_sent_date,
                self.client.contract_signed_date,
                self.client.questionnaire_sent_date,
                self.client.onboarding_complete_date,
            )
            if step_date
        )

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
        supervision_items = list(self.client.supervision_items.order_by("-created_at"))
        # Supervision items are interleaved with the session timeline so feedback
        # from supervision sits next to the sessions it refers to when preparing
        # the next one. A discussed item lands on the day it was discussed (that's
        # when the feedback arrived); an open one on the day it was raised.
        log_entries = sorted(
            chain(
                [{"type": "session", "date": s.session_date, "obj": s} for s in sessions_qs],
                [{"type": "note", "date": n.note_date, "obj": n} for n in notes_qs],
                [
                    {
                        "type": "supervision",
                        "date": item.resolved_date or item.created_at.date(),
                        "obj": item,
                    }
                    for item in supervision_items
                ],
            ),
            key=lambda e: e["date"],
            reverse=True,
        )
        # The newest session with a note is shown unfolded, so the latest work reads without
        # a click; older ones fold away, which keeps the timeline scannable.
        open_note_session_id = next(
            (e["obj"].pk for e in log_entries if e["type"] == "session" and _has_note(e["obj"])),
            None,
        )

        gebueh_diagnostic_count = 0
        if self.client.needs_gebueh_invoice:
            from ..models.gebueh import Leistungserfassung

            gebueh_diagnostic_count = Leistungserfassung.objects.filter(
                session__client=self.client,
                ziffer__nummer__in=["1", "19.5", "19.6"],
            ).count()

        return {
            "legacy_profile": profile,
            "case_sheet": build_case_sheet(self.client),
            # Named like the field it stands for, so privacy mode treats it as personal data.
            "case_summary": {"arbeitsdiagnose": working_diagnosis(self.client)},
            "intake_steps_done": intake_steps_done,
            "log_entries": log_entries,
            "open_note_session_id": open_note_session_id,
            "recent_sessions_needing_log": recent_sessions_needing_log,
            "no_log_needed_session_ids": no_log_needed_session_ids,
            "open_supervision_count": sum(
                1 for item in supervision_items if item.status == SupervisionItem.Status.OFFEN
            ),
            "session_type_choices": SessionLog.SessionType.choices,
            "mood_tag_choices": MoodTag.choices,
            "for_next_time": build_for_next_time(self.client),
            "digest": self._digest_context(),
            "documents": self.client.documents.order_by("-document_date", "-created_at"),
            "doc_type_choices": ClientDocument.DOC_TYPE_CHOICES,
            "gebueh_diagnostic_count": gebueh_diagnostic_count,
            "available_questionnaires": list_available_questionnaires(),
        }
