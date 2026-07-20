"""
Operational checklist models for tracking backup/recovery procedure completions.
Part of P-012: Operational Checklist (Backup & Recovery Automation)
"""

from datetime import date
from enum import StrEnum

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

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

    # Wording matches utils/dashboard_widgets.py's CHECKLIST_CADENCES — keep in sync.
    CHECKLIST_TYPES = [
        (ChecklistType.WEEKLY, _("Weekly backup")),
        (ChecklistType.MONTHLY, _("Monthly restore test")),
        (
            ChecklistType.QUARTERLY,
            _("MicroSD offsite backup (card A/B alternating, every 2 weeks)"),
        ),
        (ChecklistType.ANNUAL, _("Annual security review")),
    ]

    checklist_type = models.CharField(
        max_length=20,
        choices=CHECKLIST_TYPES,
        verbose_name=_("Checklist type"),
    )
    year_month = models.DateField(
        verbose_name=_("Period"),
        help_text=_("First day of the period (e.g. 2026-03-01 for March 2026)"),
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Completed on"),
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes"),
        help_text=_('e.g. "Restore test OK, 676 invoices verified"'),
    )

    class Meta:
        ordering = ["-year_month", "checklist_type"]
        unique_together = ("checklist_type", "year_month")
        verbose_name = _("Checklist completion")
        verbose_name_plural = _("Checklist completions")

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
        verbose_name=_("Checklist type"),
    )
    item_id = models.CharField(
        max_length=50,
        verbose_name=_("Item ID"),
        help_text=_("Matches the item id in CHECKLIST_ITEMS (e.g. 'pick_card')"),
    )
    reason = models.TextField(
        verbose_name=_("Reason"),
        help_text=_("Why is this step paused?"),
    )
    paused_until = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Paused until"),
        help_text=_("Empty = indefinite. Date = pause expires automatically."),
    )

    class Meta:
        unique_together = ("checklist_type", "item_id")
        verbose_name = _("Checklist pause")
        verbose_name_plural = _("Checklist pauses")

    def __str__(self) -> str:
        until = (
            self.paused_until.strftime("%d.%m.%Y") if self.paused_until else str(_("indefinite"))
        )
        return f"⏸ {self.checklist_type}/{self.item_id} ({_('until')} {until})"

    @property
    def is_active(self) -> bool:
        """Return True if this pause is still in effect today."""
        if self.paused_until is None:
            return True
        return date.today() <= self.paused_until
