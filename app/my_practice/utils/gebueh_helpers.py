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
      vereinbarter_betrag — from Leistungserfassung (frozen) or item.rate as fallback
      restbetrag          — max(0, vereinbarter_betrag - gebueh_sum)
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
        vereinbarter_betrag = leistungen[0].vereinbarter_betrag if leistungen else item.rate
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
