"""
Client alias model for bank name matching.

Handles name variations in bank statements (parent payments, legal name changes, etc.).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from .base import TimestampedModel


class ClientAlias(TimestampedModel):
    """
    Alternative names for clients as they appear in bank statements.

    Use cases:
    - Parent paying for minor's therapy
    - Legal name changes (marriage, etc.)
    - Bank account holder name differs from client name
    - International character variations (ü → ue)

    Example:
        Client: "Anna Schmidt"
        Aliases: ["A. Schmidt", "Schmidt, Anna", "Hans Schmidt" (parent)]
    """

    client = models.ForeignKey(
        "Client",
        on_delete=models.CASCADE,
        related_name="payment_aliases",
        verbose_name=_("Client"),
    )
    alias_name = models.CharField(
        max_length=200,
        verbose_name=_("Bank name"),
        help_text=_("Name as it appears on bank statements"),
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes"),
        help_text=_("e.g. 'Parent pays' or 'Former surname'"),
    )

    class Meta:
        verbose_name = _("Client alias")
        verbose_name_plural = _("Client aliases")
        unique_together = [["client", "alias_name"]]
        indexes = [
            models.Index(fields=["alias_name"]),
        ]
        ordering = ["client", "alias_name"]

    def __str__(self) -> str:
        return f"{self.alias_name} → {self.client.client_code}"
