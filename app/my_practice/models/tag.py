"""Tag models for client organization"""

from enum import StrEnum
from typing import Any

from django.db import models

from .base import TimestampedModel


class ClientTag(TimestampedModel):
    """Tag that can be assigned to clients for organization and filtering"""

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
        (Color.RED, "Rot"),
        (Color.ORANGE, "Orange"),
        (Color.YELLOW, "Gelb"),
        (Color.GREEN, "Grün"),
        (Color.BLUE, "Blau"),
        (Color.PURPLE, "Lila"),
        (Color.PINK, "Rosa"),
        (Color.GRAY, "Grau"),
    ]

    TAG_CATEGORIES = [
        (Category.GENERAL, "Allgemein"),
        (Category.ATTENTION, "Benötigt Aufmerksamkeit"),
        (Category.EXIT, "Austrittsgründe"),
    ]

    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Name",
        help_text="Tag name (e.g., 'missing-paperwork', 'follow-up')",
    )
    slug = models.SlugField(
        max_length=50,
        unique=True,
        verbose_name="Slug",
        help_text="URL-friendly version of the name (auto-generated)",
    )
    color = models.CharField(
        max_length=20,
        choices=TAG_COLORS,
        default="blue",
        verbose_name="Farbe",
        help_text="Display color for the tag",
    )
    category = models.CharField(
        max_length=20,
        choices=TAG_CATEGORIES,
        default="general",
        verbose_name="Kategorie",
        help_text="Tag category: General (informational), Needs Attention (priority), or Exit Reasons (documentation)",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Beschreibung",
        help_text="Optional description of what this tag represents",
    )
    is_system = models.BooleanField(
        default=False,
        verbose_name="Systemtag",
        help_text="System-generated tags (like 'no-next-session') cannot be manually edited",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Klient-Tag"
        verbose_name_plural = "Klient-Tags"

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
