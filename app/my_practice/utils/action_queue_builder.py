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

Each widget builder owns its own get_action_items() method; this builder
only aggregates and sorts.
"""

from datetime import date

from .dashboard_widgets import (
    BankImportReminderWidgetBuilder,
    ChecklistWidgetBuilder,
    ClientAttentionWidgetBuilder,
    InvoiceActionsWidgetBuilder,
    TaxQuarterWidgetBuilder,
)


class ActionQueueBuilder:
    """
    Aggregates action items from five widget builders into one ranked queue.

    Usage:
        builder = ActionQueueBuilder(practice)
        items = builder.build()   # list of item dicts, sorted by priority
    """

    def __init__(self, practice, today: date | None = None) -> None:
        self.practice = practice
        self.today = today or date.today()

    def build(self) -> list[dict]:
        """Return all action items sorted by (priority, sort_key)."""
        today = self.today
        all_items: list[dict] = [
            *InvoiceActionsWidgetBuilder(self.practice).get_action_items(today),
            *ClientAttentionWidgetBuilder(self.practice).get_action_items(today),
            *TaxQuarterWidgetBuilder(self.practice).get_action_items(today),
            *ChecklistWidgetBuilder().get_action_items(today),
            *BankImportReminderWidgetBuilder(self.practice).get_action_items(today),
        ]
        return [
            {k: v for k, v in item.items() if k != "_sort_key"}
            for item in sorted(all_items, key=lambda x: (x["priority"], x.get("_sort_key", "")))
        ]
