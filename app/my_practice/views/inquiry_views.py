"""Views for client inquiry / lead tracking (P-031)."""

from datetime import date, timedelta
from typing import cast

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import (
    Case,
    Count,
    IntegerField,
    Value,
    When,
)
from django.db.models.functions import TruncMonth
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View

from ..inquiry_forms import InquiryConvertForm, InquiryForm, MarketingPeriodForm
from ..models import Client, ClientInquiry, InquiryStatus, MarketingPeriod
from ..utils import DateRangeHelper
from ..utils.practice_days import berlin_public_holidays
from .crud_mixins import (
    PracticeScopedCreateView,
    PracticeScopedDeleteView,
    PracticeScopedListView,
    PracticeScopedUpdateView,
)

# Source display labels keyed by value — used in analytics
_SOURCE_LABELS = dict(ClientInquiry._meta.get_field("source").choices)

# Stage-appropriate copy-paste email templates (P-037 Ph-3)
_STAGE_EMAIL_TEMPLATES: dict[str, dict[str, str]] = {
    InquiryStatus.NEW: {
        "label": "Eingangsbestätigung",
        "subject": "Ihre Anfrage — Eingangsbestätigung",
        "body": (
            "Hallo <..>,\n\n"
            "Vielen Dank für Ihre Nachricht. Gerne würde ich einen Termin für ein "
            "Vorgespräch mit Ihnen vereinbaren, um mehr über Ihr Anliegen zu erfahren. "
            "Hier können wir auch gemeinsam klären, was für Sie in nächster Zeit "
            "hilfreich sein könnte.\n\n"
            "Hätten Sie Zeit für ein unverbindliches Kennenlernen (ca. 20 Minuten, "
            "per Video-Call oder Telefon)? Um einen Termin zu buchen, wählen Sie bitte "
            "'intro call' auf [Buchungs-URL] aus. "
            "Falls Sie dort kein Konto anlegen möchten, ist das kein Problem — "
            "schreiben Sie mir einfach zurück, wann ein Termin für Sie passen würde.\n\n"
            "Liebe Grüße und alles Gute,\n"
            "[Ihr Name]"
        ),
        "subject_en": "Your inquiry — Thank you for reaching out",
        "body_en": (
            "Hi <..>,\n\n"
            "Thank you for your message. I would love to arrange a time for a brief "
            "introductory meeting to learn more about what brings you here. We can "
            "also explore together what might be helpful for you going forward.\n\n"
            "Would you have time for an informal get-to-know (approx. 20 minutes, "
            "via video call or phone)? To book a time, please choose 'intro call' on "
            "[booking URL] and pick a time. "
            "And if you don't wish to create an account, that's fine — feel free to "
            "just email back a time that would suit you for an introductory call.\n\n"
            "Warm regards and all the best,\n"
            "[Your name]"
        ),
    },
    InquiryStatus.CONTACTED: {
        "label": "Terminvorschlag Vorgespräch",
        "subject": "Terminvorschlag: Vorgespräch",
        "body": (
            "Guten Tag,\n\n"
            "vielen Dank für Ihre Nachricht. Gerne würde ich einen Termin für ein "
            "Vorgespräch mit Ihnen vereinbaren. Hier können wir gemeinsam schauen, "
            "was für Sie hilfreich sein könnte.\n\n"
            "Hätten Sie Zeit für ein kurzes, unverbindliches Kennenlernen "
            "(ca. 20 Minuten, per Video-Call oder Telefon)? "
            "Hier sind einige Termine, die ich anbieten kann:\n"
            "– [Termin 1]\n"
            "– [Termin 2]\n\n"
            "Mit freundlichen Grüßen"
        ),
    },
    InquiryStatus.INTRO_MEETING: {
        "label": "Nach dem Vorgespräch",
        "subject": "Nächster Schritt nach unserem Vorgespräch",
        "body": (
            "Guten Tag,\n\n"
            "es war schön, mit Ihnen zu sprechen. Ich freue mich, eine gute Basis "
            "für eine Zusammenarbeit gefunden zu haben, und würde Sie gerne als "
            "Klient:in aufnehmen.\n\n"
            "Ich werde Ihnen als nächsten Schritt [den Aufnahmebogen / einen ersten "
            "Terminvorschlag] zusenden. Bitte melden Sie sich, wenn Sie bereit sind.\n\n"
            "Mit freundlichen Grüßen"
        ),
    },
    InquiryStatus.WAITLIST: {
        "label": "Platz frei — Wartelistenmeldung",
        "subject": "Freier Therapieplatz — Meldung von der Warteliste",
        "body": (
            "Guten Tag,\n\n"
            "ich möchte Ihnen mitteilen, dass ich derzeit wieder einen freien "
            "Therapieplatz habe und an unsere Anfrage denke.\n\n"
            "Hätten Sie weiterhin Interesse, Gespräche aufzunehmen? "
            "Ich würde mich über eine Rückmeldung bis [Datum] freuen.\n\n"
            "Mit freundlichen Grüßen"
        ),
    },
    InquiryStatus.IN_INTAKE: {
        "label": "Aufnahme — Unterlagen",
        "subject": "Unterlagen für den Aufnahmeprozess",
        "body": (
            "Guten Tag,\n\n"
            "ich freue mich, dass Sie die Aufnahme beginnen möchten. "
            "Anbei erhalten Sie den Aufnahmebogen, den ich Sie bitte ausgefüllt "
            "zurückzusenden.\n\n"
            "[Hier ggf. Link oder Anhang anfügen]\n\n"
            "Bei Fragen können Sie sich jederzeit bei mir melden.\n\n"
            "Mit freundlichen Grüßen"
        ),
    },
    InquiryStatus.DECLINED: {
        "label": "Freundliche Absage",
        "subject": "Rückmeldung zu Ihrer Anfrage",
        "body": (
            "Guten Tag,\n\n"
            "vielen Dank für Ihr Vertrauen und Ihre Anfrage. Nach sorgfältiger "
            "Überlegung muss ich Ihnen leider mitteilen, dass ich Sie zum "
            "jetzigen Zeitpunkt nicht aufnehmen kann.\n\n"
            "Ich empfehle Ihnen, sich an andere Kolleg:innen zu wenden "
            "(z. B. über die Suche unter therapiesuche.de). "
            "In dringenden Fällen steht Ihnen auch die Telefonseelsorge zur "
            "Verfügung (0800 111 0 111, kostenlos und 24h erreichbar).\n\n"
            "Ich wünsche Ihnen alles Gute.\n\n"
            "Mit freundlichen Grüßen"
        ),
    },
    InquiryStatus.NOT_SUITABLE: {
        "label": "Freundliche Absage (kein Match)",
        "subject": "Rückmeldung zu Ihrer Anfrage",
        "body": (
            "Guten Tag,\n\n"
            "vielen Dank für Ihr Vertrauen und Ihre Anfrage. Nach unserem Gespräch "
            "bin ich zu dem Schluss gekommen, dass ich leider nicht die beste "
            "Anlaufstelle für Sie bin — nicht weil Ihr Anliegen unwichtig wäre, "
            "sondern weil ich einen anderen Schwerpunkt habe.\n\n"
            "Ich empfehle Ihnen, sich an Kolleg:innen mit dem Schwerpunkt "
            "[Bereich] zu wenden. Über therapiesuche.de oder die Telefonseelsorge "
            "(0800 111 0 111) können Sie weitere Unterstützung finden.\n\n"
            "Ich wünsche Ihnen alles Gute.\n\n"
            "Mit freundlichen Grüßen"
        ),
    },
    InquiryStatus.UNREACHABLE: {
        "label": "Abschluss — nicht erreichbar",
        "subject": "Letzte Nachricht — Schließung der Anfrage",
        "body": (
            "Guten Tag,\n\n"
            "ich habe mehrfach versucht, Sie zu erreichen, leider ohne Erfolg. "
            "Ich werde die Anfrage daher vorerst schließen.\n\n"
            "Sollten Sie weiterhin Interesse haben, steht es Ihnen jederzeit frei, "
            "sich erneut bei mir zu melden.\n\n"
            "Mit freundlichen Grüßen"
        ),
    },
}


def _interpolate_inquiry_template(template: dict, inquiry: ClientInquiry, practice) -> dict:
    """Return a copy of the template dict with runtime values substituted."""
    first_name = inquiry.full_name.split()[0] if inquiry.full_name else ""
    practitioner = practice.name or ""
    booking = practice.booking_url or "[Buchungs-URL]"
    booking_en = practice.booking_url or "[booking URL]"

    def _sub(text: str) -> str:
        return (
            text.replace("<..>", first_name)
            .replace("[Buchungs-URL]", booking)
            .replace("[booking URL]", booking_en)
            .replace("[Ihr Name]", practitioner)
            .replace("[Your name]", practitioner)
        )

    result = dict(template)
    if "body" in result:
        result["body"] = _sub(result["body"])
    if "body_en" in result:
        result["body_en"] = _sub(result["body_en"])
    return result


def _build_inquiry_analytics(request) -> dict:
    """Compute funnel counts, time-in-stage averages, source breakdown, and monthly trend."""
    base_qs = ClientInquiry.objects.for_current_practice(request)

    # --- Funnel counts by status ---
    status_counts: dict[str, int] = {
        row["status"]: row["count"] for row in base_qs.values("status").annotate(count=Count("id"))
    }

    open_pipeline = [
        (InquiryStatus.NEW, "Neu"),
        (InquiryStatus.CONTACTED, "Kontaktiert"),
        (InquiryStatus.INTRO_MEETING, "Vorgespräch"),
        (InquiryStatus.WAITLIST, "Warteliste"),
        (InquiryStatus.IN_INTAKE, "Aufnahme"),
        (InquiryStatus.CONVERTED, "Aufgenommen"),
    ]
    funnel_stages = [(s, label, status_counts.get(s, 0)) for s, label in open_pipeline]

    closed_count = sum(
        status_counts.get(s, 0)
        for s in (InquiryStatus.DECLINED, InquiryStatus.UNREACHABLE, InquiryStatus.NOT_SUITABLE)
    )

    # --- Time-in-stage averages (working days, Mon–Fri excl. Berlin public holidays) ---
    # Pre-build a holiday set covering all inquiry years (plus the next, for year-spanning cases).
    _inquiry_years = {d.year for d in base_qs.dates("inquiry_date", "year")}
    _holidays: set[date] = set()
    for yr in _inquiry_years:
        _holidays |= berlin_public_holidays(yr)
        _holidays |= berlin_public_holidays(yr + 1)

    def _avg_days(from_field: str, to_field: str) -> tuple[float | None, int]:
        pairs = list(
            base_qs.filter(
                **{f"{from_field}__isnull": False, f"{to_field}__isnull": False}
            ).values_list(from_field, to_field)
        )
        if not pairs:
            return None, 0
        # count_working_days is inclusive; use d2 - 1 day so only days *elapsed before* the
        # milestone are counted (same-day response = 0 working days).
        total = sum(
            DateRangeHelper.count_working_days(d1, d2 - timedelta(days=1), _holidays)
            for d1, d2 in pairs
            if d2 > d1
        )
        return round(total / len(pairs), 1), len(pairs)

    avg_to_contact, n_contact = _avg_days("inquiry_date", "contacted_date")
    avg_to_intro, n_intro = _avg_days("contacted_date", "intro_date")
    avg_to_decision, n_decision = _avg_days("intro_date", "decision_date")
    avg_to_converted, n_converted = _avg_days("decision_date", "converted_date")

    time_in_stage = [
        ("Eingang → Rückmeldung", avg_to_contact, n_contact),
        ("Rückmeldung → Vorgespräch", avg_to_intro, n_intro),
        ("Vorgespräch → Entscheidung", avg_to_decision, n_decision),
        ("Entscheidung → Aufgenommen", avg_to_converted, n_converted),
    ]

    # --- Source breakdown ---
    source_rows = list(base_qs.values("source").annotate(count=Count("id")).order_by("-count"))
    total = sum(r["count"] for r in source_rows) or 1
    source_breakdown = [
        {
            "source": r["source"],
            "label": _SOURCE_LABELS.get(r["source"], r["source"]),
            "count": r["count"],
            "pct": round(100 * r["count"] / total),
        }
        for r in source_rows
    ]

    # --- Language breakdown ---
    lang_rows = list(base_qs.values("language").annotate(count=Count("id")).order_by("-count"))
    lang_total = sum(r["count"] for r in lang_rows) or 1
    _lang_labels = {"de": "Deutsch", "en": "English"}
    language_breakdown = [
        {
            "language": r["language"],
            "label": _lang_labels.get(r["language"], r["language"]),
            "count": r["count"],
            "pct": round(100 * r["count"] / lang_total),
        }
        for r in lang_rows
    ]

    # --- Monthly trend (last 12 months, by inquiry_date) ---
    range_start = DateRangeHelper.add_months(date(date.today().year, date.today().month, 1), -11)
    monthly_raw = (
        base_qs.filter(inquiry_date__gte=range_start)
        .annotate(month=TruncMonth("inquiry_date"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    max_monthly = max((row["count"] for row in monthly_raw), default=1)
    monthly_trend = [
        {
            "month": row["month"].strftime("%b %y"),
            "count": row["count"],
            "pct": round(100 * row["count"] / max_monthly),
        }
        for row in monthly_raw
    ]

    return {
        "funnel_stages": funnel_stages,
        "closed_count": closed_count,
        "time_in_stage": time_in_stage,
        "source_breakdown": source_breakdown,
        "language_breakdown": language_breakdown,
        "monthly_trend": monthly_trend,
        "total_inquiries": sum(status_counts.values()),
    }


class InquiryListView(PracticeScopedListView):
    """List all inquiries for the current practice, with optional status/source filter."""

    model = ClientInquiry
    template_name = "my_practice/inquiry_list.html"
    context_object_name = "inquiries"

    def get_queryset(self):
        qs = super().get_queryset().select_related("converted_client")
        status = self.request.GET.get("status")
        source = self.request.GET.get("source")
        # Default: hide closed inquiries unless explicitly requested
        if not self.request.GET.get("show_closed") and not status:
            qs = qs.open()
        if status:
            qs = qs.filter(status=status)
        if source:
            qs = qs.filter(source=source)
        # Sort by pipeline stage, then newest first within each stage
        status_priority = Case(
            When(status=InquiryStatus.NEW, then=Value(0)),
            When(status=InquiryStatus.CONTACTED, then=Value(1)),
            When(status=InquiryStatus.INTRO_MEETING, then=Value(2)),
            When(status=InquiryStatus.WAITLIST, then=Value(3)),
            When(status=InquiryStatus.IN_INTAKE, then=Value(3)),
            When(status=InquiryStatus.CONVERTED, then=Value(4)),
            When(status=InquiryStatus.DECLINED, then=Value(5)),
            When(status=InquiryStatus.UNREACHABLE, then=Value(5)),
            When(status=InquiryStatus.NOT_SUITABLE, then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )
        return qs.annotate(status_priority=status_priority).order_by(
            "status_priority", "-created_at"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_filter"] = self.request.GET.get("status", "")
        context["source_filter"] = self.request.GET.get("source", "")
        context["show_closed"] = bool(self.request.GET.get("show_closed"))
        context["status_choices"] = ClientInquiry._meta.get_field("status").choices
        context["source_choices"] = ClientInquiry._meta.get_field("source").choices
        context["marketing_periods"] = MarketingPeriod.objects.filter(
            practice=self.request.current_practice
        ).order_by("-start_date")
        analytics = _build_inquiry_analytics(self.request)
        context["analytics"] = analytics
        context["closed_count"] = analytics["closed_count"]
        return context


class InquiryCreateView(PracticeScopedCreateView):
    """Create a new inquiry."""

    model = ClientInquiry
    form_class = InquiryForm
    template_name = "my_practice/inquiry_form.html"
    success_url = reverse_lazy("inquiry_list")
    success_message = "Anfrage von {obj.full_name} erfasst."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action"] = "Erstellen"
        return context


class InquiryUpdateView(PracticeScopedUpdateView):
    """Edit an existing inquiry."""

    model = ClientInquiry
    form_class = InquiryForm
    template_name = "my_practice/inquiry_form.html"
    success_url = reverse_lazy("inquiry_list")
    success_message = "Anfrage von {obj.full_name} gespeichert."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action"] = "Bearbeiten"
        context["show_convert_button"] = (
            self.object.status != InquiryStatus.CONVERTED and self.object.converted_client is None
        )
        context["current_status"] = self.object.status
        context["all_email_templates"] = [
            {
                "status": status,
                "label": t["label"],
                "subject": t.get("subject", ""),
                "body": t.get("body", ""),
                "subject_en": t.get("subject_en", ""),
                "body_en": t.get("body_en", ""),
            }
            for status, t in (
                (s, _interpolate_inquiry_template(tmpl, self.object, self.request.current_practice))
                for s, tmpl in _STAGE_EMAIL_TEMPLATES.items()
            )
        ]
        return context


class InquiryDeleteView(PracticeScopedDeleteView):
    """Delete an inquiry."""

    model = ClientInquiry
    template_name = "my_practice/inquiry_confirm_delete.html"
    success_url = reverse_lazy("inquiry_list")
    context_object_name = "inquiry"
    success_message = "Anfrage von {obj.full_name} gelöscht."


class MarketingPeriodCreateView(PracticeScopedCreateView):
    """Create a new marketing period."""

    model = MarketingPeriod
    form_class = MarketingPeriodForm
    template_name = "my_practice/marketing_period_form.html"
    success_url = reverse_lazy("inquiry_list")
    success_message = "Marketing-Zeitraum erfasst."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action"] = "Erstellen"
        return context


class MarketingPeriodUpdateView(PracticeScopedUpdateView):
    """Edit an existing marketing period."""

    model = MarketingPeriod
    form_class = MarketingPeriodForm
    template_name = "my_practice/marketing_period_form.html"
    success_url = reverse_lazy("inquiry_list")
    success_message = "Marketing-Zeitraum gespeichert."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action"] = "Bearbeiten"
        return context


class MarketingPeriodDeleteView(PracticeScopedDeleteView):
    """Delete a marketing period."""

    model = MarketingPeriod
    template_name = "my_practice/marketing_period_confirm_delete.html"
    success_url = reverse_lazy("inquiry_list")
    context_object_name = "period"
    success_message = "Marketing-Zeitraum gelöscht."


class InquiryConvertView(LoginRequiredMixin, View):
    """
    Convert an inquiry to a Client.

    GET: Show confirmation form pre-filled with inquiry data.
    POST: Create the Client, link it to the inquiry, set status=CONVERTED.
    """

    def _get_inquiry(self, request: HttpRequest, pk: int) -> ClientInquiry:
        return cast(
            ClientInquiry,
            get_object_or_404(
                ClientInquiry.objects.for_current_practice(request),
                pk=pk,
            ),
        )

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        inquiry = self._get_inquiry(request, pk)
        form = InquiryConvertForm()
        return render(
            request,
            "my_practice/inquiry_convert_confirm.html",
            {"inquiry": inquiry, "form": form},
        )

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        inquiry = self._get_inquiry(request, pk)
        form = InquiryConvertForm(request.POST)

        if not form.is_valid():
            return render(
                request,
                "my_practice/inquiry_convert_confirm.html",
                {"inquiry": inquiry, "form": form},
            )

        client = Client.objects.create(
            practice=request.current_practice,
            full_name=inquiry.full_name,
            email=inquiry.email,
            phone=inquiry.phone,
            client_code=form.cleaned_data["client_code"],
            first_seen_date=form.cleaned_data.get("first_seen_date"),
            hourly_rate_60=form.cleaned_data["default_hourly_rate"],
            hourly_rate_90=form.cleaned_data["default_hourly_rate"],
            language=inquiry.language,
        )

        inquiry.converted_client = client
        inquiry.status = InquiryStatus.CONVERTED
        if not inquiry.converted_date:
            inquiry.converted_date = date.today()
        inquiry.save(update_fields=["converted_client", "status", "converted_date", "updated_at"])

        messages.success(
            request,
            f"Klient:in {client.full_name} ({client.client_code}) wurde erfolgreich angelegt.",
        )
        return redirect(reverse("client_detail", kwargs={"pk": client.pk}))
