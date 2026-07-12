"""
GebüH billing helpers shared between the PDF API view and the invoice detail view.
"""

from decimal import Decimal

from ..models import Client, Invoice


def get_arbeitsdiagnose(client: Client) -> str:
    """Return the Arbeitsdiagnose from ClientProfile, or empty string if not set."""
    try:
        return client.clientprofile.arbeitsdiagnose or ""
    except Exception:
        return ""


def build_gebueh_blocks(invoice: Invoice) -> list[dict]:
    """
    Build per-session GebüH data for invoice PDF and detail rendering.

    Returns one dict per InvoiceItem:
      item                — the InvoiceItem
      leistungen          — list of Leistungserfassung (empty if none recorded)
      gebueh_sum          — sum of all betrag values
      vereinbarter_betrag — item.total, i.e. the amount actually billed (can be
                             below the GebüH satz_max sum — providers are free to
                             charge less than a code's maximum rate)
      restbetrag          — max(0, vereinbarter_betrag - gebueh_sum), the portion
                             billed above what the GebüH codes alone cover
    """
    blocks = []
    items = invoice.items.select_related("session", "service_type").prefetch_related(
        "session__gebueh_leistungen__ziffer"
    )
    for item in items:
        leistungen = (
            list(
                item.session.gebueh_leistungen.select_related("ziffer").order_by(
                    "ziffer__sort_order"
                )
            )
            if item.session_id
            else []
        )
        gebueh_sum = sum((le.betrag for le in leistungen), Decimal("0"))
        vereinbarter_betrag = item.total
        restbetrag = max(Decimal("0"), vereinbarter_betrag - gebueh_sum)
        blocks.append(
            {
                "item": item,
                "leistungen": leistungen,
                "gebueh_sum": gebueh_sum,
                "vereinbarter_betrag": vereinbarter_betrag,
                "restbetrag": restbetrag,
            }
        )
    return blocks


def gebueh_total_for_blocks(blocks: list[dict]) -> Decimal:
    """Return the running total of gebueh_sum across all blocks (0 if none/empty)."""
    return sum((b["gebueh_sum"] for b in blocks), Decimal("0"))
