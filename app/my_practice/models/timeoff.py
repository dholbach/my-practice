"""Time off tracking model for holidays and vacation"""

from datetime import date
from enum import StrEnum

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from .base import TimestampedModel


class TimeOff(TimestampedModel):
    """Track holidays, vacation time, and other periods when practice is closed"""

    class Type(StrEnum):
        VACATION = "vacation"
        HOLIDAY = "holiday"
        SICK = "sick"
        TRAINING = "training"
        OTHER = "other"

    # Deliberately bilingual (not wrapped) — same pattern as CompanyWithdrawal/
    # CompanyExpense's Meta.verbose_name: shows German and English simultaneously
    # regardless of active UI language.
    TYPE_CHOICES = [
        (Type.VACATION, "Urlaub / Vacation"),
        (Type.HOLIDAY, "Feiertag / Public Holiday"),
        (Type.SICK, "Krank / Sick Leave"),
        (Type.TRAINING, "Fortbildung / Training"),
        (Type.OTHER, "Sonstiges / Other"),
    ]

    start_date = models.DateField(verbose_name=_("Start Date"))
    end_date = models.DateField(verbose_name=_("End Date"))
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default="vacation",
        verbose_name=_("Type"),
    )
    title = models.CharField(
        max_length=200,
        verbose_name=_("Title"),
        help_text=_("Brief description (e.g., 'Sommerurlaub', 'Weihnachten')"),
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes"),
        help_text=_("Additional information or reminders"),
    )

    class Meta:
        ordering = ["start_date"]
        verbose_name = _("Time Off")
        verbose_name_plural = _("Time Off Periods")

    def __str__(self) -> str:
        return f"{self.title} ({self.start_date} - {self.end_date})"

    def clean(self) -> None:
        """Validate that end_date is not before start_date"""
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": _("End date cannot be before start date.")})

    @property
    def duration_days(self) -> int:
        """Calculate duration in days"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0

    @property
    def is_current(self) -> bool:
        """Check if time off period includes today"""
        today = date.today()
        return self.start_date <= today <= self.end_date

    @property
    def is_upcoming(self) -> bool:
        """Check if time off is in the future"""
        return self.start_date > date.today()

    @property
    def is_past(self) -> bool:
        """Check if time off is in the past"""
        return self.end_date < date.today()
