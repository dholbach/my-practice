"""Service type model for billable services"""

from django.db import models

from .base import PracticeScopedManager


class ServiceType(models.Model):
    """Service types for invoice items (internal names, will be translated in invoice templates)"""

    # Practice relationship
    practice = models.ForeignKey(
        "Practice",
        on_delete=models.PROTECT,
        related_name="service_types",
        verbose_name="Praxis",
        null=True,  # Intentionally nullable: global service types (practice=None) are shared across all practices
        blank=True,
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Code",
        help_text="Internal identifier (e.g., therapy_60, therapy_90)",
    )
    name = models.CharField(
        max_length=255,
        verbose_name="Name (Default)",
        help_text='Display name (e.g., "60-Min Therapy Session")',
    )
    name_de = models.CharField(
        max_length=255,
        verbose_name="Name (Deutsch)",
        blank=True,
        help_text='German name (e.g., "Psychotherapie, 60 Min.")',
    )
    name_en = models.CharField(
        max_length=255,
        verbose_name="Name (English)",
        blank=True,
        help_text='English name (e.g., "60-Min Therapy Session")',
    )
    default_duration = models.IntegerField(default=60, verbose_name="Standarddauer (Minuten)")

    # Practice-scoped manager
    objects = PracticeScopedManager()

    class Meta:
        verbose_name = "Leistungsart"
        verbose_name_plural = "Leistungsarten"
        ordering = ["code"]

    def __str__(self) -> str:
        return self.name

    def get_name(self, language: str = "de") -> str:
        """Get name in specified language, fallback to default name"""
        if language == "de" and self.name_de:
            return self.name_de
        elif language == "en" and self.name_en:
            return self.name_en
        return self.name
