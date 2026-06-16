"""
Views for operational checklist feature (P-012).
Handles checklist display and completion tracking.
"""

from datetime import date, timedelta

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView

from ..models import ChecklistItemPause, OperationalChecklistCompletion

# Checklist items per type.
#
# IMPORTANT FOR SELF-HOSTERS: These items reflect one specific backup setup
# (LUKS-encrypted USB drive + NAS + MicroSD offsite rotation). The checklist
# engine (completion tracking, pausing, dashboard widget) is fully reusable —
# but you MUST replace the items below with steps that match your own backup
# and operational procedures. See docs/operations/SECURITY.md for context.
CHECKLIST_ITEMS: dict[str, list[dict[str, str]]] = {
    "weekly": [
        {"id": "connect_usb", "title": "Externe USB-Festplatte an Laptop anschließen"},
        {
            "id": "run_backup",
            "title": "Backup-Befehl ausführen (./dev.py backup oder scripts/backup.sh)",
        },
        {"id": "verify_logs", "title": "USB- und NAS-Backup-Logs auf Fehler prüfen"},
        {
            "id": "nas_trigger",
            "title": "Bestätigen, dass NAS-Backup automatisch ausgelöst wurde",
        },
        {"id": "disconnect_usb", "title": "USB-Festplatte sicher trennen"},
    ],
    "monthly": [
        {
            "id": "pick_source",
            "title": "Zufällige Backup-Quelle auswählen (USB oder NAS)",
        },
        {
            "id": "decrypt",
            "title": "Backup entschlüsseln (Passphrase aus versiegeltem Umschlag)",
        },
        {"id": "restore_db", "title": "Datenbank auf Test-Instanz wiederherstellen"},
        {
            "id": "verify_counts",
            "title": "Rechnungsanzahl & Klientenanzahl mit Produktion vergleichen",
        },
        {
            "id": "test_media",
            "title": "Eine Mediendatei herunterladen und Prüfsumme verifizieren",
        },
        {
            "id": "log_result",
            "title": 'Ergebnis protokollieren: "Restore-Test [DATUM] [USB/NAS] [Anzahl Datensätze] ✅"',
        },
    ],
    "quarterly": [
        # Rotate every 2 weeks — alternate between Card A and Card B (UHS-I is fine, e.g. SanDisk Ultra / Samsung EVO Plus 32–64 GB)
        {
            "id": "pick_card",
            "title": "Andere Karte aus dem Schrank nehmen (Karte A und Karte B im Wechsel)",
        },
        {
            "id": "copy_backup",
            "title": "Neueste Pika-Backup-Momentaufnahme auf Karte kopieren",
        },
        {
            "id": "encrypt_card",
            "title": "Karte verschlüsseln (gleiche Passphrase wie USB/NAS)",
        },
        {
            "id": "test_restore",
            "title": "Kurztest: 1–2 Dateien + Datenbankanzahl auf Lesbarkeit prüfen",
        },
        {
            "id": "label_card",
            "title": 'Karte beschriften: "Karte A/B — [Datum]"',
        },
        {
            "id": "store_card",
            "title": "Im abgeschlossenen Schrank lagern (separater Ort vom Laptop)",
        },
    ],
    "annual": [
        {
            "id": "microsd_restore",
            "title": "Vollständiger Restore-Test von MicroSD (Offsite-Szenario)",
        },
        {
            "id": "update_check",
            "title": "Backup-Tool-Versionen & Sicherheitsupdates prüfen",
        },
        {
            "id": "dpia_review",
            "title": "DPIA-Dokument auf Verarbeitungsänderungen prüfen",
        },
        {
            "id": "audit_logs",
            "title": "Backup-Logs überprüfen (keine unerklärten Fehler)",
        },
        {
            "id": "refresh_plan",
            "title": "Notfallzugangsplan (P-010) bei Bedarf aktualisieren",
        },
    ],
}


def _get_period_start(checklist_type: str) -> date:
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


class OperationalChecklistView(TemplateView):
    """Display a checklist page for the given type and current period."""

    template_name = "my_practice/checklist.html"

    def get_context_data(self, **kwargs: object) -> dict:
        context = super().get_context_data(**kwargs)
        checklist_type = self.kwargs.get("checklist_type", "monthly")

        # Validate type
        valid_types: dict[str, str] = dict(OperationalChecklistCompletion.CHECKLIST_TYPES)
        if checklist_type not in valid_types:
            checklist_type = "monthly"

        period_start = _get_period_start(checklist_type)

        # Get or create the entry for this period (not yet completed)
        checklist, _ = OperationalChecklistCompletion.objects.get_or_create(
            checklist_type=checklist_type,
            year_month=period_start,
        )

        # Load active pauses and annotate each item
        active_pauses = {
            p.item_id: p
            for p in ChecklistItemPause.objects.filter(checklist_type=checklist_type)
            if p.is_active
        }
        annotated_items = [
            {**item, "pause": active_pauses.get(item["id"])}
            for item in CHECKLIST_ITEMS.get(checklist_type, [])
        ]

        context.update(
            {
                "checklist": checklist,
                "checklist_type": checklist_type,
                "checklist_type_display": valid_types[checklist_type],
                "items": annotated_items,
                "period_start": period_start,
                "all_types": list(valid_types.items()),
            }
        )
        return context


def checklist_complete(request: HttpRequest, checklist_type: str) -> HttpResponse:
    """Mark a checklist as completed for the current period."""
    if request.method != "POST":
        return redirect("checklist", checklist_type=checklist_type)

    valid_types: dict[str, str] = dict(OperationalChecklistCompletion.CHECKLIST_TYPES)
    if checklist_type not in valid_types:
        messages.error(request, "Unbekannter Checklisten-Typ.")
        return redirect("dashboard")

    period_start = _get_period_start(checklist_type)
    checklist = get_object_or_404(
        OperationalChecklistCompletion,
        checklist_type=checklist_type,
        year_month=period_start,
    )

    if checklist.is_completed:
        messages.info(request, f"{valid_types[checklist_type]} wurde bereits abgeschlossen.")
        return redirect("checklist", checklist_type=checklist_type)

    notes = request.POST.get("notes", "").strip()
    checklist.mark_complete(notes=notes)

    messages.success(
        request,
        f"✅ {valid_types[checklist_type]} für {period_start.strftime('%B %Y')} abgeschlossen.",
    )
    return redirect("checklist", checklist_type=checklist_type)


def checklist_pause_item(request: HttpRequest, checklist_type: str, item_id: str) -> HttpResponse:
    """POST: Create or update a pause for a specific checklist item."""
    if request.method != "POST":
        return redirect("checklist", checklist_type=checklist_type)

    valid_types = dict(OperationalChecklistCompletion.CHECKLIST_TYPES)
    if checklist_type not in valid_types:
        return redirect("dashboard")

    valid_item_ids = {item["id"] for item in CHECKLIST_ITEMS.get(checklist_type, [])}
    if item_id not in valid_item_ids:
        messages.error(request, "Unbekanntes Checklisten-Element.")
        return redirect("checklist", checklist_type=checklist_type)

    reason = request.POST.get("reason", "").strip()
    paused_until_str = request.POST.get("paused_until", "").strip()
    paused_until = None
    if paused_until_str:
        from datetime import datetime

        try:
            paused_until = datetime.strptime(paused_until_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    ChecklistItemPause.objects.update_or_create(
        checklist_type=checklist_type,
        item_id=item_id,
        defaults={"reason": reason, "paused_until": paused_until},
    )
    messages.success(request, "⏸ Element pausiert.")
    return redirect("checklist", checklist_type=checklist_type)


def checklist_unpause_item(request: HttpRequest, checklist_type: str, item_id: str) -> HttpResponse:
    """POST: Remove the pause for a specific checklist item."""
    if request.method != "POST":
        return redirect("checklist", checklist_type=checklist_type)

    ChecklistItemPause.objects.filter(checklist_type=checklist_type, item_id=item_id).delete()
    messages.success(request, "▶️ Pause aufgehoben.")
    return redirect("checklist", checklist_type=checklist_type)


_BOILERPLATE_CARDS: list[dict] = [
    {
        "title": "Keine Kassenerstattung (Privatpraxis)",
        "id": "kasse",
        "body_de": (
            "Guten Tag,\n\n"
            "ich möchte Sie darauf hinweisen, dass meine Praxis als Privatpraxis "
            "geführt wird. Das bedeutet, dass die Kosten in der Regel nicht direkt "
            "von der gesetzlichen Krankenversicherung übernommen werden.\n\n"
            "Gesetzlich Versicherte können die Honorarnoten jedoch bei ihrer Kasse "
            "einreichen – eine Erstattung ist möglich, liegt aber im Ermessen der "
            "jeweiligen Kasse. Ich stelle Ihnen gerne eine formgerechte Rechnung aus.\n\n"
            "Bei Fragen stehe ich Ihnen gerne zur Verfügung.\n\n"
            "Mit freundlichen Grüßen"
        ),
        "body_en": (
            "Dear Sir/Madam,\n\n"
            "please note that my practice operates on a private-pay basis. This means "
            "that costs are generally not directly reimbursed by statutory health "
            "insurance (GKV).\n\n"
            "However, patients with statutory insurance may submit invoices to their "
            "insurer for reimbursement — approval is at the insurer's discretion. "
            "I will issue formal invoices on request.\n\n"
            "Please feel free to contact me if you have any questions.\n\n"
            "Kind regards"
        ),
    },
    {
        "title": "Kein freier Platz / Warteliste",
        "id": "warteliste",
        "body_de": (
            "Guten Tag,\n\n"
            "vielen Dank für Ihre Nachricht. Leider habe ich derzeit keinen freien "
            "Therapieplatz. Ich führe jedoch eine Warteliste und würde Sie gerne "
            "darauf aufnehmen.\n\n"
            "Sobald ein Platz frei wird, melde ich mich bei Ihnen. Bitte beachten "
            "Sie, dass dies einige Monate dauern kann.\n\n"
            "In dringenden Fällen empfehle ich Ihnen, sich an die "
            "Terminservicestelle Ihrer Krankenkasse oder an einen psychiatrischen "
            "Notfalldienst zu wenden.\n\n"
            "Mit freundlichen Grüßen"
        ),
        "body_en": (
            "Dear Sir/Madam,\n\n"
            "thank you for reaching out. Unfortunately I do not have any therapy "
            "slots available at this time. I do maintain a waiting list and would "
            "be happy to add you to it.\n\n"
            "I will contact you as soon as a place becomes available. Please note "
            "that this may take several months.\n\n"
            "In urgent cases, I recommend contacting your health insurer's "
            "appointment service or an emergency psychiatric service.\n\n"
            "Kind regards"
        ),
    },
    {
        "title": "Terminverschiebung / Absage",
        "id": "absage",
        "body_de": (
            "Guten Tag,\n\n"
            "ich schreibe Ihnen bezüglich unseres Termins am [Datum]. Leider muss "
            "ich diesen Termin verschieben / absagen.\n\n"
            "Ich möchte Ihnen folgende Ausweichtermine anbieten:\n"
            "– [Datum 1]\n"
            "– [Datum 2]\n\n"
            "Bitte geben Sie mir kurz Bescheid, welcher Termin für Sie passt, oder "
            "ob Sie einen anderen Zeitraum bevorzugen.\n\n"
            "Ich entschuldige mich für die Unannehmlichkeiten und freue mich darauf, "
            "Sie bald zu einem neuen Termin zu empfangen.\n\n"
            "Mit freundlichen Grüßen"
        ),
        "body_en": (
            "Dear Sir/Madam,\n\n"
            "I am writing regarding our appointment on [date]. Unfortunately I need "
            "to reschedule / cancel this appointment.\n\n"
            "I would like to offer the following alternative dates:\n"
            "– [Date 1]\n"
            "– [Date 2]\n\n"
            "Please let me know which date works for you, or whether you would "
            "prefer a different time.\n\n"
            "I apologise for the inconvenience and look forward to seeing you at "
            "the rescheduled appointment.\n\n"
            "Kind regards"
        ),
    },
    {
        "title": "Abschluss / Therapieende",
        "id": "abschluss",
        "body_de": (
            "Guten Tag,\n\n"
            "wie besprochen beenden wir unsere therapeutische Zusammenarbeit mit dem "
            "[Datum]. Ich möchte Ihnen noch einmal herzlich für das entgegengebrachte "
            "Vertrauen danken.\n\n"
            "Bei Bedarf können Sie sich jederzeit wieder an mich wenden. Ich wünsche "
            "Ihnen alles Gute auf Ihrem weiteren Weg.\n\n"
            "Mit freundlichen Grüßen"
        ),
        "body_en": (
            "Dear Sir/Madam,\n\n"
            "as discussed, our therapeutic work together will conclude on [date]. "
            "I would like to sincerely thank you for the trust you have placed in me.\n\n"
            "Should you ever need support again, please do not hesitate to get in "
            "touch. I wish you all the best going forward.\n\n"
            "Kind regards"
        ),
    },
]


def boilerplate_view(request: HttpRequest) -> HttpResponse:
    """Display copyable DE/EN email text templates (P-033)."""
    from django.shortcuts import render

    return render(request, "my_practice/boilerplate.html", {"cards": _BOILERPLATE_CARDS})
