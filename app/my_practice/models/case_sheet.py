"""
The case sheet (P-006): a client's case formulation as dated, sourced lines.

Replaces the two markdown blobs on ClientProfile (intake notes, case notes) and its
working diagnosis field. A ``ClinicalFact`` is one line in one cell of the sheet; changing
a line supersedes it with a new one and closing it marks it resolved, so what was written
before, and when, stays on record (the corrections-leave-the-original rule of § 630f BGB).

The rows of the sheet are defined here in code, not as model choices, so adding or
renaming a row needs no migration. Row and cell labels are authored Somatic Experiencing
vocabulary in German, like the intake template they replace, and are not wrapped for i18n
(CODEBASE_STANDARDS § Internationalisation).
"""

from dataclasses import dataclass

from django.db import models
from django.utils.translation import gettext_lazy as _

from ..fields import EncryptedTextField
from .base import TimestampedModel
from .client import Client
from .session import Session


@dataclass(frozen=True)
class SheetCell:
    """A labelled sub-cell of a row (e.g. "Beginn" under "Symptomatik")."""

    key: str
    label: str


@dataclass(frozen=True)
class SheetRow:
    """One row of the case sheet.

    ``cells`` is empty for a row that is a single cell; otherwise each cell has its own
    lines. ``multi`` rows hold several lines side by side (triggers, resources …); the
    others hold one current line, which adding a new one supersedes.
    """

    kind: str
    label: str
    multi: bool = False
    cells: tuple[SheetCell, ...] = ()


CASE_SHEET_ROWS: tuple[SheetRow, ...] = (
    SheetRow("concern", "Anliegen"),
    SheetRow(
        "symptoms",
        "Symptomatik",
        cells=(
            SheetCell("onset", "Beginn"),
            SheetCell("change", "Verschlimmerung / Änderung"),
            SheetCell("until", "Dauer bis"),
        ),
    ),
    SheetRow("physical", "Körperlich", multi=True),
    SheetRow("affective", "Affektiv", multi=True),
    SheetRow("first_trigger", "Erst-Auslöser"),
    SheetRow("current_triggers", "Akt. Trigger", multi=True),
    SheetRow("history", "Anamnestische Besonderheiten"),
    SheetRow(
        "ans", "Nervensystem / ANS", cells=(SheetCell("arousal", "Erregungslage, Grundmuster"),)
    ),
    SheetRow(
        "limbic",
        "Limbisches System",
        cells=(
            SheetCell("closeness", "Nähe-/Distanzmuster"),
            SheetCell("empathy", "Empathiefähigkeit"),
            SheetCell("loyalty", "Loyalität / Scham / Schuld"),
        ),
    ),
    SheetRow(
        "neocortical",
        "Neocortical",
        cells=(
            SheetCell("presence", "Präsenz / Fokusstabilität"),
            SheetCell("mentalization", "Mentalisationsgrad"),
        ),
    ),
    SheetRow("beliefs", "Glaubenssätze", multi=True),
    SheetRow(
        "sibam",
        "SIBAM-Elemente",
        cells=(SheetCell("preferred", "bevorzugt"), SheetCell("missing", "fehlend")),
    ),
    SheetRow("resources", "Ressourcen", multi=True),
    SheetRow("hypothesis", "Arbeitshypothese"),
    SheetRow("diagnosis", "Arbeitsdiagnose"),
    SheetRow("goal", "Therapieziel (Patient)"),
    SheetRow("safety", "„Sicherheit“ gestört durch"),
    SheetRow("process", "Prozessaufbau"),
    SheetRow("in_their_words", "O-Töne", multi=True),
    SheetRow("themes", "Themen", multi=True),
    SheetRow("family", "Familiendynamik", multi=True),
    SheetRow("i_thou", "Ich-Du", multi=True),
    SheetRow("challenges", "Herausforderungen", multi=True),
    SheetRow("future_work", "Zukünftige Arbeit / Fragen", multi=True),
    # Text from the old notes that matched no row (an unknown heading, a leftover) lands here.
    SheetRow("notes", "Weitere Notizen", multi=True),
)

ROWS_BY_KIND: dict[str, SheetRow] = {row.kind: row for row in CASE_SHEET_ROWS}


def cell_keys(row: SheetRow) -> tuple[str, ...]:
    """The ``sub`` values a row accepts: its cells' keys, or just "" for a single-cell row."""
    return tuple(cell.key for cell in row.cells) or ("",)


class ClinicalFact(TimestampedModel):
    """One dated line of a client's case sheet (encrypted)."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        SUPERSEDED = "superseded", _("Superseded")
        RESOLVED = "resolved", _("Resolved")

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="clinical_facts",
        verbose_name=_("Client"),
    )

    # NOT encrypted: which row and cell a line belongs to says nothing about the client
    kind = models.CharField(max_length=30, verbose_name=_("Row"))
    sub = models.CharField(max_length=30, blank=True, default="", verbose_name=_("Cell"))

    content = EncryptedTextField(
        verbose_name=_("Content"),
        help_text=_("The line as written (encrypted, Markdown supported)"),
    )

    noted_on = models.DateField(verbose_name=_("Noted on"))

    # The session whose log this line came from, when it was added from one
    source_session = models.ForeignKey(
        Session,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="clinical_facts",
        verbose_name=_("Source session"),
    )

    # NOT encrypted: used to pick the lines that are current
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name=_("Status"),
    )
    # When it stopped being current (superseded or resolved)
    closed_on = models.DateField(null=True, blank=True, verbose_name=_("Closed on"))
    superseded_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supersedes",
        verbose_name=_("Superseded by"),
    )

    class Meta:
        verbose_name = _("Case sheet line")
        verbose_name_plural = _("Case sheet lines")
        ordering = ["noted_on", "pk"]
        indexes = [
            models.Index(fields=["client", "kind", "status"], name="clinicalfact_client_kind_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.client.client_code} · {self.kind}"
