"""
Shared output formatting helpers.

These exist so that the same value renders identically wherever it is shown —
in a template, in a PDF, or in the body of a client-facing email. Formatting
money inline (e.g. ``f"{invoice.total:.2f} €"``) silently produces English
number format and diverges from the rest of the app; use these instead.
"""

from decimal import Decimal


def format_currency_de(value: Decimal | float | int, symbol: str = "€") -> str:
    """Format a number as currency in German/EU convention.

    Period as thousands separator, comma as decimal separator, and a
    non-breaking space before the symbol so the amount never wraps away
    from its currency sign.

    Example: ``Decimal("11064.03")`` -> ``"11.064,03 €"`` (with U+00A0)
    """
    # Format US-style first, then swap the separators via a placeholder so the
    # two replacements can't clobber each other.
    formatted = f"{float(value):,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted}\u00a0{symbol}"  # U+00A0, written as an escape on purpose
