"""
ActionQueueBuilder — aggregates action items from all dashboard widget
builders into a single ranked queue for the "Braucht Aktion" pane (P-117).

Each item in the queue has the schema:
    priority        int  1 = urgent (red), 2 = warning (amber), 3 = info (blue)
    category        str  English key: "INVOICE" | "DRAFT" | "CLIENT" | "TAX" | "OPS"
    category_label  str  German display label (e.g. "Rechnung") — translate in P-039
    summary         str  One-line description shown in the row
    sub_text        str  Secondary line (client code, amount, date — optional)
    action_url      str  URL for the primary action button
    action_label    str  Button label

Items are sorted by (priority, sort_key) — most urgent first.
"""

from datetime import date
from decimal import Decimal

from django.urls import reverse

from .dashboard_widgets import (
    BankImportReminderWidgetBuilder,
    ChecklistWidgetBuilder,
    ClientAttentionWidgetBuilder,
    InvoiceActionsWidgetBuilder,
    TaxQuarterWidgetBuilder,
)


def _fmt_eur(amount: Decimal) -> str:
    """Format amount in German currency style: 1.234,56 €"""
    formatted = f"{float(amount):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} €"


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
        all_items: list[dict] = [
            *self._invoice_items(),
            *self._client_items(),
            *self._tax_items(),
            *self._checklist_items(),
            *self._bank_items(),
        ]
        return [
            {k: v for k, v in item.items() if k != "_sort_key"}
            for item in sorted(all_items, key=lambda x: (x["priority"], x.get("_sort_key", "")))
        ]

    # ── Item factories ────────────────────────────────────────────────────────

    def _make_invoice_item(self, inv, priority: int, action_url: str, action_label: str) -> dict:
        age = (self.today - inv.invoice_date).days
        return {
            "priority": priority,
            "category": "INVOICE",
            "category_label": "Rechnung",
            "summary": f"{inv.invoice_number} · {age} Tage offen",
            "sub_text": f"{inv.client.client_code} · {_fmt_eur(inv.total)}",
            "action_url": action_url,
            "action_label": action_label,
            "_sort_key": str(inv.invoice_date),
        }

    def _make_client_item(self, client, summary: str) -> dict:
        return {
            "priority": 2,
            "category": "CLIENT",
            "category_label": "Klient",
            "summary": summary,
            "sub_text": "",
            "action_url": reverse("client_detail", kwargs={"pk": client.pk}),
            "action_label": "Anzeigen",
            "_sort_key": client.client_code,
        }

    # ── Invoice sources ───────────────────────────────────────────────────────

    def _invoice_items(self) -> list[dict]:
        ctx = InvoiceActionsWidgetBuilder(self.practice).build_context()

        overdue = [
            self._make_invoice_item(
                inv,
                1,
                reverse("send_payment_reminder", kwargs={"pk": inv.client.pk}),
                "Mahnen",
            )
            for inv in ctx["overdue_invoices"]
        ]

        drafts: list[dict] = []
        for inv in ctx["draft_invoices"]:
            last_session = getattr(inv, "last_session_date", None)
            sub = inv.client.client_code
            if last_session:
                sub += f" · letzte Sitzung {last_session.strftime('%d.%m.%Y')}"
            drafts.append(
                {
                    "priority": 2,
                    "category": "DRAFT",
                    "category_label": "Entwurf",
                    "summary": f"{inv.invoice_number} versandbereit",
                    "sub_text": sub,
                    "action_url": reverse("invoice_edit", kwargs={"pk": inv.pk}),
                    "action_label": "Fertigstellen",
                    "_sort_key": str(last_session or inv.invoice_date),
                }
            )

        overdue_ids = {inv.pk for inv in ctx["overdue_invoices"]}
        unpaid = [
            self._make_invoice_item(
                inv,
                2,
                reverse("invoice_detail", kwargs={"pk": inv.pk}),
                "Anzeigen",
            )
            for inv in ctx["unpaid_invoices"]
            if inv.pk not in overdue_ids
        ]

        return [*overdue, *drafts, *unpaid]

    # ── Client attention sources ───────────────────────────────────────────────

    def _client_items(self) -> list[dict]:
        ctx = ClientAttentionWidgetBuilder(self.practice).build_context()

        tagged = [
            self._make_client_item(client, f"{client.client_code} — {tag_name}")
            for tag_name, data in ctx["tagged_clients"].items()
            for client in data["clients"]
        ]

        tagged_ids = {c.pk for data in ctx["tagged_clients"].values() for c in data["clients"]}
        inactive = [
            self._make_client_item(client, f"{client.client_code} — keine Sitzung seit 60+ Tagen")
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
                "category": "TAX",
                "category_label": "Steuer",
                "summary": f"Q{ctx['current_quarter']} {self.today.year} · Vorauszahlung fehlt",
                "sub_text": f"Umsatz: {_fmt_eur(revenue)}",
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
                "category": "OPS",
                "category_label": "Betrieb",
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
                "category": "OPS",
                "category_label": "Betrieb",
                "summary": summary,
                "sub_text": "",
                "action_url": ctx["import_url"],
                "action_label": "Importieren",
                "_sort_key": "",
            }
        ]
