"""
Practice TODO/Task tracking model.
For managing practice-related tasks, notes, and weekly planning.
"""

from enum import StrEnum
from typing import TYPE_CHECKING

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .base import PracticeScopedManager, TimestampedModel

if TYPE_CHECKING:
    pass


class PracticeTodo(TimestampedModel):
    """
    TODO/Task item for a practice.

    Supports:
    - Weekly planning ("get receipt for XYZ")
    - Learning tasks ("read up on ABC")
    - Administrative tasks ("book ticket for conference")
    - Completion tracking with timestamps
    - Historical review ("what did I complete last month?")
    """

    class Category(StrEnum):
        ADMIN = "admin"
        LEARNING = "learning"
        FINANCIAL = "financial"
        CLIENT = "client"
        PRACTICE = "practice"
        OTHER = "other"

    class Priority(StrEnum):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        URGENT = "urgent"

    CATEGORY_CHOICES = [
        (Category.ADMIN, _("Administrative")),
        (Category.LEARNING, _("Learning/Research")),
        (Category.FINANCIAL, _("Financial/Accounting")),
        (Category.CLIENT, _("Client-related")),
        (Category.PRACTICE, _("Practice Management")),
        (Category.OTHER, _("Other")),
    ]

    PRIORITY_CHOICES = [
        (Priority.LOW, _("Low")),
        (Priority.MEDIUM, _("Medium")),
        (Priority.HIGH, _("High")),
        (Priority.URGENT, _("Urgent")),
    ]

    # Practice relationship
    practice = models.ForeignKey(
        "Practice",
        on_delete=models.PROTECT,
        related_name="todos",
        verbose_name=_("Practice"),
    )

    # Core fields
    title = models.CharField(max_length=255, help_text=_("Short description of the task"))
    description = models.TextField(blank=True, help_text=_("Optional detailed notes"))
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="other",
        help_text=_("Task category for organization"),
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default="medium",
        help_text=_("Task priority level"),
    )
    is_focus = models.BooleanField(
        default=False,
        help_text=_("Mark as a focus task for the current week"),
        verbose_name=_("Focus task"),
    )

    # Dates
    due_date = models.DateField(null=True, blank=True, help_text=_("Optional due date"))
    completed_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When the task was completed")
    )

    # Practice-scoped manager
    objects = PracticeScopedManager()

    class Meta:
        verbose_name = _("Task")
        verbose_name_plural = _("Tasks")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["practice", "completed_at"], name="todo_prac_completed"),
            models.Index(fields=["practice", "due_date"], name="todo_prac_due"),
            models.Index(fields=["practice", "category"], name="todo_prac_category"),
        ]

    def __str__(self) -> str:
        status = "✅" if self.is_completed else "⏳"
        return f"{status} {self.title}"

    @property
    def is_completed(self) -> bool:
        """Check if task is completed."""
        return self.completed_at is not None

    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if self.is_completed or not self.due_date:
            return False
        return self.due_date < timezone.now().date()

    def mark_completed(self) -> None:
        """Mark task as completed with current timestamp."""
        if not self.completed_at:
            self.completed_at = timezone.now()
            self.save(update_fields=["completed_at"])

    def mark_incomplete(self) -> None:
        """Mark task as incomplete."""
        if self.completed_at:
            self.completed_at = None
            self.save(update_fields=["completed_at"])
