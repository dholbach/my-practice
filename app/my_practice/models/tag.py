"""Tag models for client organization"""

from enum import StrEnum
from typing import Any

from django.db import models
from django.utils.translation import gettext_lazy as _

from .base import TimestampedModel


class ClientTag(TimestampedModel):
    """Tag that can be assigned to clients for organization and filtering.

    Tags are deliberately global (no practice FK) because this app targets a
    single-operator scenario where one person owns all practices. A global tag
    vocabulary keeps the UI simple and avoids duplicate tag management per
    practice. Tag names can therefore be seen by any practice — do not encode
    client-identifying information in tag names.
    """

    class Color(StrEnum):
        RED = "red"
        ORANGE = "orange"
        YELLOW = "yellow"
        GREEN = "green"
        BLUE = "blue"
        PURPLE = "purple"
        PINK = "pink"
        GRAY = "gray"

    class Category(StrEnum):
        GENERAL = "general"
        ATTENTION = "attention"
        EXIT = "exit"

    TAG_COLORS = [
        (Color.RED, _("Red")),
        (Color.ORANGE, _("Orange")),
        (Color.YELLOW, _("Yellow")),
        (Color.GREEN, _("Green")),
        (Color.BLUE, _("Blue")),
        (Color.PURPLE, _("Purple")),
        (Color.PINK, _("Pink")),
        (Color.GRAY, _("Gray")),
    ]

    TAG_CATEGORIES = [
        (Category.GENERAL, _("General")),
        (Category.ATTENTION, _("Needs attention")),
        (Category.EXIT, _("Exit reasons")),
    ]

    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_("Name"),
        help_text=_("Tag name (e.g., 'missing-paperwork', 'follow-up')"),
    )
    slug = models.SlugField(
        max_length=50,
        unique=True,
        verbose_name=_("Slug"),
        help_text=_("URL-friendly version of the name (auto-generated)"),
    )
    color = models.CharField(
        max_length=20,
        choices=TAG_COLORS,
        default="blue",
        verbose_name=_("Color"),
        help_text=_("Display color for the tag"),
    )
    category = models.CharField(
        max_length=20,
        choices=TAG_CATEGORIES,
        default="general",
        verbose_name=_("Category"),
        help_text=_(
            "Tag category: General (informational), Needs Attention (priority), or Exit Reasons (documentation)"
        ),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Optional description of what this tag represents"),
    )
    is_system = models.BooleanField(
        default=False,
        verbose_name=_("System tag"),
        help_text=_("System-generated tags (like 'no-next-session') cannot be manually edited"),
    )

    class Meta:
        ordering = ["name"]
        verbose_name = _("Client tag")
        verbose_name_plural = _("Client tags")

    @property
    def category_priority(self) -> int:
        """Get numeric priority for sorting (1=attention, 2=general, 3=exit)"""
        priority_map = {"attention": 1, "general": 2, "exit": 3}
        return priority_map.get(self.category, 99)

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Auto-generate slug from name if not provided"""
        if not self.slug:
            from django.utils.text import slugify

            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
