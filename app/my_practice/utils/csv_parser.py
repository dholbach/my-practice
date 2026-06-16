"""
CSV parsing utilities for importing invoice data.
"""

from decimal import Decimal


def parse_german_decimal(value_str: str) -> Decimal:
    """
    Parse German decimal format (comma as decimal separator).

    Args:
        value_str: String like "340,00" or "113,33"

    Returns:
        Decimal value

    Raises:
        InvalidOperation: If string cannot be parsed
    """
    if not value_str:
        return Decimal("0.00")

    # Remove whitespace and € symbol
    value_str = value_str.strip().replace("€", "").replace(" ", "")

    # Handle different number formats:
    # German: 1.234,56 (dot = thousand, comma = decimal)
    # US/Mixed: 1,234.56 (comma = thousand, dot = decimal)
    # Simple: 1234.56 or 1234,56

    has_comma = "," in value_str
    has_dot = "." in value_str

    if has_comma and has_dot:
        # Both present - determine which is decimal separator
        # The one appearing last is the decimal separator
        last_comma_pos = value_str.rfind(",")
        last_dot_pos = value_str.rfind(".")

        if last_comma_pos > last_dot_pos:
            # German format: 1.234,56
            value_str = value_str.replace(".", "")
            value_str = value_str.replace(",", ".")
        else:
            # US format: 1,234.56
            value_str = value_str.replace(",", "")
    elif has_comma:
        # Only comma - could be German decimal or thousand separator
        # If comma is followed by exactly 2 digits at the end, it's decimal
        # Otherwise it's thousand separator
        if value_str.rstrip("-+").split(",")[-1].isdigit() and len(value_str.split(",")[-1]) <= 2:
            # German decimal: 123,45
            value_str = value_str.replace(",", ".")
        else:
            # Thousand separator: 1,234
            value_str = value_str.replace(",", "")
    # If only dot or neither, assume English format or integer

    return Decimal(value_str).quantize(Decimal("0.01"))
