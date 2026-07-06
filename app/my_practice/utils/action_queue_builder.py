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
Multiple items of the same category/type are grouped into a single row.
"""

from datetime import date
from decimal import Decimal

from django.db.models import Max
from django.urls import reverse

from ..models import Session
from .dashboard_widgets import (
    BankImportReminderWidgetBuilder,
    ChecklistWidgetBuilder,
    ClientAttentionWidgetBuilder,
    InvoiceActionsWidgetBuilder,
    TaxQuarterWidgetBuilder,
)

_TAG_LABELS: dict[str, str] = {
    "follow-up": "Follow-up",
    "pause": "Pause",
    "ending": "Abschluss",
    "missing-session-log": "Protokoll fehlt",
}


def _fmt_eur(amount: Decimal) -> str:
    """Format amount in German currency style: 1.234,56 €"""
    formatted = f"{float(amount):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} €"


def _join_truncated(items: list[str], total: int, sep: str = ", ", max_shown: int = 4) -> str:
    """Join up to max_shown items; append ' …' if total exceeds that."""
    # str() coerces lazy translation proxies, which join() rejects
    shown = [str(item) for item in items[:max_shown]]
    result = sep.join(shown)
    if total > len(shown):
        result += " …"
    return result


class ActionQueueBuilder:
    """
    Aggregates action items from five existing widget builders into one
    ranked queue. Items of the same type are grouped into a single row.

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

    def _make_client_item(self, client, summary: str, action_label: str = "Anzeigen") -> dict:
        return {
            "priority": 2,
            "category": "CLIENT",
            "category_label": "Klient",
            "summary": summary,
            "sub_text": "",
            "action_url": reverse("client_detail", kwargs={"pk": client.pk}),
            "action_label": action_label,
            "_sort_key": client.client_code,
        }

    # ── Invoice sources ───────────────────────────────────────────────────────

    def _invoice_items(self) -> list[dict]:
        ctx = InvoiceActionsWidgetBuilder(self.practice).build_context()
        items: list[dict] = []

        # Overdue — group into one priority-1 row
        n_overdue = ctx["overdue_count"]
        if n_overdue > 0:
            invoices = list(ctx["overdue_invoices"])
            total = ctx["overdue_total"]
            codes = _join_truncated(
                list(dict.fromkeys(inv.client.client_code for inv in invoices)),
                n_overdue,
            )
            oldest_age = max((self.today - inv.invoice_date).days for inv in invoices)
            items.append(
                {
                    "priority": 1,
                    "category": "INVOICE",
                    "category_label": "Rechnung",
                    "summary": f"{n_overdue} überfällig · {_fmt_eur(total)}",
                    "sub_text": f"{codes} · >{oldest_age} Tage",
                    "action_url": reverse("invoice_list") + "?status=sent",
                    "action_label": "Mahnen",
                    "_sort_key": "0_overdue",
                }
            )

        # Drafts — group into one row
        n_drafts = ctx["draft_count"]
        if n_drafts > 0:
            invoices = list(ctx["draft_invoices"])
            nums = _join_truncated([inv.invoice_number for inv in invoices], n_drafts, sep=" · ")
            label = "Rechnung bereit" if n_drafts == 1 else "Rechnungen bereit"
            items.append(
                {
                    "priority": 2,
                    "category": "DRAFT",
                    "category_label": "Entwurf",
                    "summary": f"{n_drafts} {label} zum Senden",
                    "sub_text": nums,
                    "action_url": reverse("invoice_list") + "?status=draft",
                    "action_label": "Fertigstellen",
                    "_sort_key": "1_drafts",
                }
            )

        return items

    # ── Client attention sources ───────────────────────────────────────────────

    def _client_items(self) -> list[dict]:
        ctx = ClientAttentionWidgetBuilder(self.practice).build_context()

        tagged = [
            {
                **self._make_client_item(
                    client,
                    f"{client.client_code} · {_TAG_LABELS.get(tag_name, tag_name)}",
                    action_label="Öffnen",
                ),
            }
            for tag_name, data in ctx["tagged_clients"].items()
            for client in data["clients"]
        ]

        tagged_ids = {c.pk for data in ctx["tagged_clients"].values() for c in data["clients"]}
        inactive_clients = [c for c in ctx["no_recent_session_clients"] if c.pk not in tagged_ids]

        inactive = self._build_inactive_items(inactive_clients)

        return tagged + inactive

    def _build_inactive_items(self, clients: list) -> list[dict]:
        """Build action items for inactive clients, annotated with last session date."""
        if not clients:
            return []

        client_ids = [c.pk for c in clients]
        last_sessions: dict = dict(
            Session.objects.filter(client_id__in=client_ids, cancelled=False)
            .values("client_id")
            .annotate(last=Max("session_date"))
            .values_list("client_id", "last")
        )

        items = []
        for client in clients:
            last_date = last_sessions.get(client.pk)
            if last_date:
                days = (self.today - last_date).days
                summary = f"{client.client_code} · keine Sitzung seit {days} T"
                sub = f"zuletzt {last_date.strftime('%d.%m.%Y')}"
                sort_key = f"inactive_{999 - days:04d}"
            else:
                summary = f"{client.client_code} · noch keine Sitzung"
                sub = ""
                sort_key = "inactive_9999"
            items.append(
                {
                    **self._make_client_item(client, summary, action_label="Kontakt"),
                    "sub_text": sub,
                    "_sort_key": sort_key,
                }
            )
        return items

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
                "_sort_key": "0_tax",
            }
        ]

    # ── Operational checklists ────────────────────────────────────────────────

    def _checklist_items(self) -> list[dict]:
        ctx = ChecklistWidgetBuilder().build_context()
        entries = ctx["pending_checklists"]
        if not entries:
            return []
        n = len(entries)
        label = "Checkliste fällig" if n == 1 else "Checklisten fällig"
        sub = _join_truncated([e["label"] for e in entries], n, sep=" · ", max_shown=3)
        return [
            {
                "priority": 2,
                "category": "OPS",
                "category_label": "Betrieb",
                "summary": f"{n} {label}",
                "sub_text": sub,
                "action_url": reverse("checklist", kwargs={"checklist_type": entries[0]["type"]}),
                "action_label": "Ansehen",
                "_sort_key": str(entries[0]["period_start"]),
            }
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
