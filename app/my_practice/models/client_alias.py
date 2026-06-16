"""
Client alias model for bank name matching.

Handles name variations in bank statements (parent payments, legal name changes, etc.).
"""

from django.db import models

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
        verbose_name="Klient",
    )
    alias_name = models.CharField(
        max_length=200,
        verbose_name="Bank-Name",
        help_text="Name wie er auf Kontoauszügen erscheint",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notizen",
        help_text="z.B. 'Mutter zahlt' oder 'Alter Nachname'",
    )

    class Meta:
        verbose_name = "Klienten-Alias"
        verbose_name_plural = "Klienten-Aliase"
        unique_together = [["client", "alias_name"]]
        indexes = [
            models.Index(fields=["alias_name"]),
        ]
        ordering = ["client", "alias_name"]

    def __str__(self) -> str:
        return f"{self.alias_name} → {self.client.client_code}"
