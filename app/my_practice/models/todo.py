"""
Practice TODO/Task tracking model.
For managing practice-related tasks, notes, and weekly planning.
"""

from enum import StrEnum
from typing import TYPE_CHECKING

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .base import PracticeScopedManager, TimestampedModel

if TYPE_CHECKING:
    pass

# Maps a related_object's content type to the URL name for its detail page.
# Extend as more materialized task_types gain a linkable related_object.
_RELATED_OBJECT_URL_NAMES = {
    "client": "client_detail",
    "invoice": "invoice_detail",
}


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

    class TaskType(StrEnum):
        MANUAL = "manual"
        MISSING_SESSION_LOG = "missing_session_log"
        INVOICE_UNPAID = "invoice_unpaid"
        INVOICE_UNSENT = "invoice_unsent"
        SUPERVISION = "supervision"
        RECURRING_REVIEW = "recurring_review"
        OPERATIONAL_CHECKLIST = "operational_checklist"

    TASK_TYPE_CHOICES = [
        (TaskType.MANUAL, _("Manual")),
        (TaskType.MISSING_SESSION_LOG, _("Missing session log")),
        (TaskType.INVOICE_UNPAID, _("Unpaid invoice")),
        (TaskType.INVOICE_UNSENT, _("Unsent invoice")),
        (TaskType.SUPERVISION, _("Supervision")),
        (TaskType.RECURRING_REVIEW, _("Recurring review")),
        (TaskType.OPERATIONAL_CHECKLIST, _("Operational checklist")),
    ]

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
    snoozed_until = models.DateField(
        null=True,
        blank=True,
        help_text=_("Hide from the focus queue until this date"),
    )

    # Focus Queue (P-050): where this task originated from, and — for
    # materialized/derived types — what it's about.
    task_type = models.CharField(
        max_length=30,
        choices=TASK_TYPE_CHOICES,
        default=TaskType.MANUAL,
        help_text=_(
            "Manual entry, or a materialized system signal (unpaid invoice, "
            "missing session log, etc.)"
        ),
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text=_("Related object type, for materialized tasks (e.g. Client, Invoice)"),
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey("content_type", "object_id")

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
            models.Index(fields=["practice", "task_type"], name="todo_prac_task_type"),
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

    @property
    def is_snoozed(self) -> bool:
        """Check if task is currently snoozed."""
        return bool(self.snoozed_until and self.snoozed_until >= timezone.now().date())

    @property
    def related_object_url(self) -> str | None:
        """URL to the related object's detail page, if there is one we know how to link."""
        if self.related_object is None:
            return None
        url_name = _RELATED_OBJECT_URL_NAMES.get(self.content_type.model)
        if not url_name:
            return None
        return reverse(url_name, kwargs={"pk": self.object_id})

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
