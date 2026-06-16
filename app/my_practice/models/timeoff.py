"""Time off tracking model for holidays and vacation"""

from datetime import date
from enum import StrEnum

from django.core.exceptions import ValidationError
from django.db import models

from .base import TimestampedModel


class TimeOff(TimestampedModel):
    """Track holidays, vacation time, and other periods when practice is closed"""

    class Type(StrEnum):
        VACATION = "vacation"
        HOLIDAY = "holiday"
        SICK = "sick"
        TRAINING = "training"
        OTHER = "other"

    TYPE_CHOICES = [
        (Type.VACATION, "Urlaub / Vacation"),
        (Type.HOLIDAY, "Feiertag / Public Holiday"),
        (Type.SICK, "Krank / Sick Leave"),
        (Type.TRAINING, "Fortbildung / Training"),
        (Type.OTHER, "Sonstiges / Other"),
    ]

    start_date = models.DateField(verbose_name="Start Date")
    end_date = models.DateField(verbose_name="End Date")
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default="vacation",
        verbose_name="Type",
    )
    title = models.CharField(
        max_length=200,
        verbose_name="Title",
        help_text="Brief description (e.g., 'Sommerurlaub', 'Weihnachten')",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notes",
        help_text="Additional information or reminders",
    )

    class Meta:
        ordering = ["start_date"]
        verbose_name = "Time Off"
        verbose_name_plural = "Time Off Periods"

    def __str__(self) -> str:
        return f"{self.title} ({self.start_date} - {self.end_date})"

    def clean(self) -> None:
        """Validate that end_date is not before start_date"""
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})

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
