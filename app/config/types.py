"""
Type extensions for Django request object
"""

from typing import TYPE_CHECKING, Optional, Protocol

if TYPE_CHECKING:
    from my_practice.models import Practice


class PracticeScopedRequest(Protocol):
    """Protocol for HttpRequest with current_practice attribute added by middleware"""

    current_practice: Optional["Practice"]
