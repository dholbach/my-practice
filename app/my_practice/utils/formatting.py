"""
Shared output formatting helpers.

These exist so that the same value renders identically wherever it is shown —
in a template, in a PDF, or in the body of a client-facing email. Formatting
money inline (e.g. ``f"{invoice.total:.2f} €"``) silently produces English
number format and diverges from the rest of the app; use these instead.
"""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def to_decimal(value: Decimal | float | int | str) -> Decimal:
    """A Decimal for ``value``; a float goes through its shortest repr (0.1 -> 0.1)."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def round_money(value: Decimal | float | int | str, step: Decimal = CENT) -> Decimal:
    """Round half up to ``step`` (cents by default), as amounts on paper are rounded.

    Not ``round()``/float formatting: those round half to even on a binary
    approximation, so 2.675 became 2.67 and 2.5 became 2.
    """
    return to_decimal(value).quantize(step, rounding=ROUND_HALF_UP)


def format_currency_de(
    value: Decimal | float | int | str, symbol: str = "€", *, whole: bool = False
) -> str:
    """Format a number as currency in German/EU convention.

    Period as thousands separator, comma as decimal separator, and a
    non-breaking space before the symbol so the amount never wraps away
    from its currency sign.

    Example: ``Decimal("11064.03")`` -> ``"11.064,03 €"`` (with U+00A0);
    with ``whole=True`` it is rounded to full euros: ``"11.064 €"``.
    """
    # Format US-style first, then swap the separators via a placeholder so the
    # two replacements can't clobber each other.
    places = 0 if whole else 2
    formatted = f"{round_money(value, Decimal(1).scaleb(-places)):,.{places}f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted}\u00a0{symbol}"  # U+00A0, written as an escape on purpose
