"""
ActionQueueBuilder — aggregates action items from all dashboard widget
builders into a single ranked queue for the "Braucht Aktion" pane (P-117).

Each item in the queue has the schema:
    priority    int   1 = urgent (red), 2 = warning (amber), 3 = info (blue)
    category    str   "RECHNUNG" | "ENTWURF" | "KLIENT" | "STEUER" | "BETRIEB"
    summary     str   One-line description shown in the row
    sub_text    str   Secondary line (client code, amount, date — optional)
    action_url  str   URL for the primary action button
    action_label str  Button label

Items are sorted by (priority, sort_key) — most urgent first.
"""

from datetime import date

from django.urls import reverse

from .dashboard_widgets import (
    BankImportReminderWidgetBuilder,
    ChecklistWidgetBuilder,
    ClientAttentionWidgetBuilder,
    InvoiceActionsWidgetBuilder,
    TaxQuarterWidgetBuilder,
)


class ActionQueueBuilder:
    """
    Aggregates action items from five existing widget builders into one
    ranked queue.

    Usage:
        builder = ActionQueueBuilder(practice)
        items = builder.build()   # list of item dicts, sorted by priority
    """

    def __init__(self, practice, today: date | None = None) -> None:
        self.practice = practice
        self.today = today or date.today()

    def build(self) -> list[dict]:
        """Return all action items sorted by (priority, sort_key)."""
        items: list[dict] = []
        items.extend(self._invoice_items())
        items.extend(self._client_items())
        items.extend(self._tax_items())
        items.extend(self._checklist_items())
        items.extend(self._bank_items())
        items.sort(key=lambda x: (x["priority"], x.get("_sort_key", "")))
        for item in items:
            item.pop("_sort_key", None)
        return items

    # ── Invoice sources ───────────────────────────────────────────────────────

    def _invoice_items(self) -> list[dict]:
        ctx = InvoiceActionsWidgetBuilder(self.practice).build_context()
        items: list[dict] = []

        for inv in ctx["overdue_invoices"]:
            age = (self.today - inv.invoice_date).days
            items.append(
                {
                    "priority": 1,
                    "category": "RECHNUNG",
                    "summary": f"{inv.invoice_number} · {age} Tage offen",
                    "sub_text": f"{inv.client.client_code} · {inv.total:,.2f} €".replace(",", "."),
                    "action_url": reverse("send_payment_reminder", kwargs={"pk": inv.client.pk}),
                    "action_label": "Mahnen",
                    "_sort_key": str(inv.invoice_date),
                }
            )

        for inv in ctx["draft_invoices"]:
            last_session = getattr(inv, "last_session_date", None)
            sub = inv.client.client_code
            if last_session:
                sub += f" · letzte Sitzung {last_session.strftime('%d.%m.%Y')}"
            items.append(
                {
                    "priority": 2,
                    "category": "ENTWURF",
                    "summary": f"{inv.invoice_number} versandbereit",
                    "sub_text": sub,
                    "action_url": reverse("invoice_edit", kwargs={"pk": inv.pk}),
                    "action_label": "Fertigstellen",
                    "_sort_key": str(last_session or inv.invoice_date),
                }
            )

        overdue_ids = {inv.pk for inv in ctx["overdue_invoices"]}
        for inv in ctx["unpaid_invoices"]:
            if inv.pk in overdue_ids:
                continue
            age = (self.today - inv.invoice_date).days
            items.append(
                {
                    "priority": 2,
                    "category": "RECHNUNG",
                    "summary": f"{inv.invoice_number} · {age} Tage offen",
                    "sub_text": f"{inv.client.client_code} · {inv.total:,.2f} €".replace(",", "."),
                    "action_url": reverse("invoice_detail", kwargs={"pk": inv.pk}),
                    "action_label": "Anzeigen",
                    "_sort_key": str(inv.invoice_date),
                }
            )

        return items

    # ── Client attention sources ───────────────────────────────────────────────

    def _client_items(self) -> list[dict]:
        ctx = ClientAttentionWidgetBuilder(self.practice).build_context()

        tagged = [
            {
                "priority": 2,
                "category": "KLIENT",
                "summary": f"{client.client_code} — {tag_name}",
                "sub_text": "",
                "action_url": reverse("client_detail", kwargs={"pk": client.pk}),
                "action_label": "Anzeigen",
                "_sort_key": client.client_code,
            }
            for tag_name, data in ctx["tagged_clients"].items()
            for client in data["clients"]
        ]

        tagged_ids = {c.pk for data in ctx["tagged_clients"].values() for c in data["clients"]}
        inactive = [
            {
                "priority": 2,
                "category": "KLIENT",
                "summary": f"{client.client_code} — keine Sitzung seit 60+ Tagen",
                "sub_text": "",
                "action_url": reverse("client_detail", kwargs={"pk": client.pk}),
                "action_label": "Anzeigen",
                "_sort_key": client.client_code,
            }
            for client in ctx["no_recent_session_clients"]
            if client.pk not in tagged_ids
        ]

        return tagged + inactive

    # ── Tax prepayment ────────────────────────────────────────────────────────

    def _tax_items(self) -> list[dict]:
        ctx = TaxQuarterWidgetBuilder(self.practice).build_context()
        if not ctx["show_warning"]:
            return []
        revenue = ctx["quarter_revenue"]
        return [
            {
                "priority": 1,
                "category": "STEUER",
                "summary": f"Q{ctx['current_quarter']} {self.today.year} · Vorauszahlung fehlt",
                "sub_text": f"Umsatz: {revenue:,.2f} €".replace(",", "."),
                "action_url": ctx["add_payment_url"],
                "action_label": "Eintragen",
                "_sort_key": "",
            }
        ]

    # ── Operational checklists ────────────────────────────────────────────────

    def _checklist_items(self) -> list[dict]:
        ctx = ChecklistWidgetBuilder().build_context()
        return [
            {
                "priority": 2,
                "category": "BETRIEB",
                "summary": entry["label"],
                "sub_text": f"Fällig seit {entry['period_start'].strftime('%d.%m.%Y')}",
                "action_url": reverse("checklist", kwargs={"checklist_type": entry["type"]}),
                "action_label": "Erledigen",
                "_sort_key": str(entry["period_start"]),
            }
            for entry in ctx["pending_checklists"]
        ]

    # ── Bank import reminder ──────────────────────────────────────────────────

    def _bank_items(self) -> list[dict]:
        ctx = BankImportReminderWidgetBuilder(self.practice).build_context()
        if not ctx["show_reminder"]:
            return []
        days = ctx["days_since_import"]
        summary = (
            f"Letzter Bank-Import vor {days} Tagen"
            if days is not None
            else "Noch keine Kontoauszüge importiert"
        )
        return [
            {
                "priority": 3,
                "category": "BETRIEB",
                "summary": summary,
                "sub_text": "",
                "action_url": ctx["import_url"],
                "action_label": "Importieren",
                "_sort_key": "",
            }
        ]
