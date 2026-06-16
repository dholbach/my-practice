"""
Operational checklist models for tracking backup/recovery procedure completions.
Part of P-012: Operational Checklist (Backup & Recovery Automation)
"""

from datetime import date
from enum import StrEnum

from django.db import models
from django.utils import timezone

from .base import TimestampedModel


class OperationalChecklistCompletion(models.Model):
    """
    Record of a completed operational checklist for a specific period.

    Each checklist type has one entry per period (week/month/quarter/year).
    The unique_together constraint prevents duplicate completions.
    """

    class ChecklistType(StrEnum):
        WEEKLY = "weekly"
        MONTHLY = "monthly"
        QUARTERLY = "quarterly"
        ANNUAL = "annual"

    CHECKLIST_TYPES = [
        (ChecklistType.WEEKLY, "Wöchentliche Sicherung"),
        (ChecklistType.MONTHLY, "Monatlicher Restore-Test"),
        (ChecklistType.QUARTERLY, "MicroSD-Offsite-Backup (Karte A/B im Wechsel, alle 2 Wochen)"),
        (ChecklistType.ANNUAL, "Jährliche Sicherheitsüberprüfung"),
    ]

    checklist_type = models.CharField(
        max_length=20,
        choices=CHECKLIST_TYPES,
        verbose_name="Checklisten-Typ",
    )
    year_month = models.DateField(
        verbose_name="Periode",
        help_text="First day of the period (e.g. 2026-03-01 for March 2026)",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Abgeschlossen am",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notizen",
        help_text='z.B. "Restore-Test OK, 676 Rechnungen verifiziert"',
    )

    class Meta:
        ordering = ["-year_month", "checklist_type"]
        unique_together = ("checklist_type", "year_month")
        verbose_name = "Checklisten-Abschluss"
        verbose_name_plural = "Checklisten-Abschlüsse"

    def __str__(self) -> str:
        status = "✅" if self.completed_at else "⏳"
        return f"{status} {self.get_checklist_type_display()} ({self.year_month.strftime('%B %Y')})"

    @property
    def is_completed(self) -> bool:
        """Return True if this checklist has been marked complete."""
        return self.completed_at is not None

    def mark_complete(self, notes: str = "") -> None:
        """Mark this checklist as completed now."""
        self.completed_at = timezone.now()
        if notes:
            self.notes = notes
        self.save()


class ChecklistItemPause(TimestampedModel):
    """
    Pause an individual checklist item indefinitely or until a specific date.

    One record per (checklist_type, item_id) — updating the record replaces
    any previous pause. Delete the record to unpause.

    Examples:
        - quarterly/new_microsd paused until 2026-04-15 ("waiting for delivery")
        - weekly/nas_trigger paused indefinitely ("NAS not yet set up")
    """

    CHECKLIST_TYPES = OperationalChecklistCompletion.CHECKLIST_TYPES

    checklist_type = models.CharField(
        max_length=20,
        choices=CHECKLIST_TYPES,
        verbose_name="Checklisten-Typ",
    )
    item_id = models.CharField(
        max_length=50,
        verbose_name="Element-ID",
        help_text="Matches the item id in CHECKLIST_ITEMS (e.g. 'pick_card')",
    )
    reason = models.TextField(
        verbose_name="Grund",
        help_text="Warum ist dieser Schritt pausiert?",
    )
    paused_until = models.DateField(
        null=True,
        blank=True,
        verbose_name="Pausiert bis",
        help_text="Leer = unbegrenzt. Datum = Pause läuft automatisch ab.",
    )

    class Meta:
        unique_together = ("checklist_type", "item_id")
        verbose_name = "Checklisten-Pause"
        verbose_name_plural = "Checklisten-Pausen"

    def __str__(self) -> str:
        until = self.paused_until.strftime("%d.%m.%Y") if self.paused_until else "unbegrenzt"
        return f"⏸ {self.checklist_type}/{self.item_id} (bis {until})"

    @property
    def is_active(self) -> bool:
        """Return True if this pause is still in effect today."""
        if self.paused_until is None:
            return True
        return date.today() <= self.paused_until
