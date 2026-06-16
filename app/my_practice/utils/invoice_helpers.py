"""
Invoice-related utility functions.
Centralized logic for invoice numbering and related operations.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from my_practice.models import Client

from ..models import Invoice


def get_next_invoice_number(client: "Client") -> str:
    """
    Calculate the next invoice number for a client.

    Invoice numbers follow the pattern: {CLIENT_CODE}-{NUMBER}
    Examples: XX-1, XX-2, YY-42, etc.

    This function finds the highest existing number for the client
    and returns the next sequential number.

    Args:
        client: Client object

    Returns:
        str: Next invoice number (e.g., "XX-17")

    Examples:
        >>> client = Client.objects.get(client_code="XX")
        >>> get_next_invoice_number(client)
        "XX-5"  # if XX-4 is the highest invoice number
    """
    # Find all invoices for this client
    existing_invoices = Invoice.objects.filter(
        invoice_number__startswith=f"{client.client_code}-"
    ).values_list("invoice_number", flat=True)

    if existing_invoices:
        # Extract numeric parts and find the highest
        numbers = []
        for invoice_number in existing_invoices:
            try:
                # Extract the numeric part after the dash
                num = int(invoice_number.split("-")[-1])
                numbers.append(num)
            except ValueError, IndexError:
                # Skip malformed invoice numbers
                continue

        if numbers:
            # Use highest number + 1
            new_num = max(numbers) + 1
        else:
            # No valid numbers found, start at 1
            new_num = 1
    else:
        # First invoice for this client
        new_num = 1

    return f"{client.client_code}-{new_num}"
