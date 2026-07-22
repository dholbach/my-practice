"""
Helper for building a client-code lookup map used across import/export flows.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Client


def build_client_map() -> dict[str, "Client"]:
    """
    Build a dictionary mapping client codes to Client instances.

    Optimized to only fetch necessary fields (id, client_code, full_name).

    Returns:
        Dict mapping client_code (str) -> Client instance

    Example:
        >>> client_map = build_client_map()
        >>> client = client_map.get('XX')  # Get client with code 'XX'
    """
    from ..models import Client

    return {
        client.client_code: client
        for client in Client.objects.only("id", "client_code", "full_name")
    }
