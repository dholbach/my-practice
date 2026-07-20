"""
Clinical documentation models (P-009).

All narrative content is encrypted at-rest using Fernet (Art. 9 DSGVO).
Session metadata (mood_tags, session_type) is stored unencrypted to enable
triage signals without requiring the Fernet key.

Models:
  ClientProfile  — per-client intake notes + running case notes + diagnosis
  SessionLog     — per-session reflection entry
  SupervisionItem — supervision agenda items, cross-client queue
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from ..fields import EncryptedCharField, EncryptedTextField
from .base import TimestampedModel
from .client import Client
from .session import Session

# ─── Preloaded template text ──────────────────────────────────────────────────
# Baked into form initial= values (not model defaults) so existing blank
# ClientProfile rows stay empty and only new forms get the boilerplate.
#
# NOT wrapped for i18n: this is authored clinical-documentation scaffolding in
# Somatic Experiencing terminology, written by/for the therapist's own German-
# language case notes — not app UI chrome that should switch with the UI
# language toggle. Same rationale as the authored bilingual email content in
# utils/email_utils.py, except this has no English counterpart to pair with
# since it's the practitioner's own working template, not client-facing.

INTAKE_NOTES_TEMPLATE = """\
## Anliegen


## Symptomatik
**Beginn:**
**Verschlimmerung/Änderung:**

## Körperlich


## Affektiv


## Erst-Auslöser


## Aktuelle Trigger


## Anamnestische Besonderheiten


## Nervensystem / ANS
**Erregungslage / Grundmuster:**

## Limbisches System
**Nähe-/Distanzmuster:**
**Empathiefähigkeit:**

## Neocortical
**Präsenz / Fokusstabilität:**

## Glaubenssätze


## SIBAM-Elemente
**Bevorzugt:**

## Ressourcen


## Arbeitshypothese


## Arbeitsdiagnose


## Therapieziel (Patient)


## "Sicherheit" gestört durch


## Prozessaufbau


## Verlauf
"""

CASE_NOTES_TEMPLATE = """\
## Themen


## Familiendynamik


## Ich-Du


## Herausforderungen


## Zukünftige Arbeit / Fragen


"""

SESSION_LOG_TEMPLATE = """\
## Gefühl danach


## Wahrnehmung


## Sitzung


## Was half
"""


# ─── Mood tag constants ────────────────────────────────────────────────────────


class MoodTag(models.TextChoices):
    """Session mood/state tags for triage signals. Stored as JSON list of keys."""

    # Session weight
    SCHWER = "schwer", _("Heavy")
    MITTEL = "mittel", _("Medium")
    LEICHT = "leicht", _("Light")

    # Client state
    HOHE_AKTIVIERUNG = "hohe_aktivierung", _("High activation")
    GUTE_RESSOURCEN = "gute_ressourcen", _("Good resources")
    KRISE = "krise", _("Crisis")
    NIEDRIG_AFFEKTIV = "niedrig_affektiv", _("Low affect")
    DISSOZIATION = "dissoziation", _("Dissociation")
    UNSICHER = "unsicher", _("Uncertain")

    # Format
    ONLINE = "online", _("Online")

    # Progress
    FORTSCHRITT = "fortschritt", _("Progress")
    UPDATE_CHITCHAT = "update_chitchat", _("Update / chitchat")
    RUECKSCHRITT = "rueckschritt", _("Setback")
    DURCHBRUCH = "durchbruch", _("Breakthrough")
    RICHTUNGSLOS = "richtungslos", _("Directionless")


# ─── Models ───────────────────────────────────────────────────────────────────


class ClientProfile(TimestampedModel):
    """
    Per-client intake record and running case notes.

    Created automatically on first access to the client documentation page.
    All content fields are Fernet-encrypted — only accessible through application code.
    """

    client = models.OneToOneField(
        Client,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name=_("Client"),
    )

    # Zone 1: intake assessment (rarely updated after intake)
    intake_notes = EncryptedTextField(
        blank=True,
        verbose_name=_("Intake & anamnesis"),
        help_text=_("Initial session + clinical assessment (encrypted)"),
    )

    # Zone 2: evolving case formulation
    case_notes = EncryptedTextField(
        blank=True,
        verbose_name=_("Case notes"),
        help_text=_("Themes, dynamics, challenges, future work (encrypted)"),
    )

    # Quick-reference diagnosis label — visible on client page overview
    arbeitsdiagnose = EncryptedCharField(
        blank=True,
        verbose_name=_("Working diagnosis"),
        help_text=_("Clinical working diagnosis (encrypted)"),
    )

    class Meta:
        verbose_name = _("Client profile")
        verbose_name_plural = _("Client profiles")

    def __str__(self) -> str:
        return f"{_('Profile')}: {self.client.client_code}"


class SessionLog(TimestampedModel):
    """
    Per-session clinical reflection entry.

    Links to the central Session object. Metadata (session_type, mood_tags) is
    stored unencrypted so triage signals can be computed without the Fernet key.
    Narrative content (content, therapist_reflection) is Fernet-encrypted.
    """

    class SessionType(models.TextChoices):
        ERSTGESPRAECH = "erstgespraech", _("Initial session")
        STANDARD = "standard", _("Standard")
        KRISENINTERVENTION = "krisenintervention", _("Crisis intervention")
        ABSCHLUSSPHASE = "abschlussphase", _("Closing phase")
        AUSFALL = "ausfall", _("No-show / cancellation")

    session = models.OneToOneField(
        Session,
        on_delete=models.CASCADE,
        related_name="log",
        verbose_name=_("Session"),
    )

    session_type = models.CharField(
        max_length=30,
        choices=SessionType.choices,
        default=SessionType.STANDARD,
        verbose_name=_("Session type"),
        # NOT encrypted — used for triage signals and basic UI labels
    )

    mood_tags = models.JSONField(
        default=list,
        verbose_name=_("Mood tags"),
        help_text=_("Selection from predefined signals (unencrypted, for triage)"),
        # NOT encrypted — enables emergency triage summary without Fernet key
    )

    summary = models.CharField(
        max_length=120,
        blank=True,
        default="",
        verbose_name=_("Short summary"),
        help_text=_("One-liner for the overview (unencrypted, max. 120 characters)"),
        # NOT encrypted — shown in the client overview cockpit without Fernet key
    )

    content = EncryptedTextField(
        blank=True,
        verbose_name=_("Session note"),
        help_text=_(
            "Pre-filled: feeling afterward / perception / session / what helped (encrypted)"
        ),
    )

    interventions = EncryptedTextField(
        blank=True,
        verbose_name=_("Interventions"),
        help_text=_("Techniques and interventions applied (encrypted)"),
    )

    therapist_reflection = EncryptedTextField(
        blank=True,
        verbose_name=_("Own reflection"),
        help_text=_("How I felt about it — countertransference (encrypted, separate)"),
    )

    next_session_ideas = EncryptedTextField(
        blank=True,
        verbose_name=_("Ideas for next session"),
        help_text=_("Themes, interventions, homework for the next session (encrypted)"),
    )

    class Meta:
        verbose_name = _("Session log")
        verbose_name_plural = _("Session logs")
        ordering = ["-session__session_date"]

    def __str__(self) -> str:
        return f"Log: {self.session}"

    @property
    def client(self) -> Client:
        """Convenience accessor."""
        return self.session.client


class SupervisionItem(TimestampedModel):
    """
    Supervision agenda item linked to a client.

    Items are shown on the client documentation page and in a cross-client
    supervision queue (open items grouped by client).
    Content is Fernet-encrypted.
    """

    class Status(models.TextChoices):
        OFFEN = "offen", _("Open")
        BESPROCHEN = "besprochen", _("Discussed")

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="supervision_items",
        verbose_name=_("Client"),
    )

    content = EncryptedTextField(
        verbose_name=_("Content"),
        help_text=_("Supervision question or topic (encrypted)"),
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OFFEN,
        verbose_name=_("Status"),
        # NOT encrypted — used for filtering open/closed items
    )

    class Meta:
        verbose_name = _("Supervision topic")
        verbose_name_plural = _("Supervision topics")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["client", "status"], name="supervision_client_status_idx"),
        ]

    def __str__(self) -> str:
        return f"Supervision {self.client.client_code} [{self.status}]"


class ClientNote(TimestampedModel):
    """
    Dated freeform note attached to a client (encrypted).

    For ad-hoc entries like phone calls, observations between sessions, and
    post-supervision reflections. Date is user-supplied (defaults to today).
    Content is Fernet-encrypted and supports markdown formatting.
    """

    class NoteType(models.TextChoices):
        NOTE = "note", _("Note")
        SUPERVISION = "supervision", _("Supervision")

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="client_notes",
        verbose_name=_("Client"),
    )

    note_date = models.DateField(
        verbose_name=_("Date"),
        help_text=_("Date of the entry (e.g. call, supervision, note)"),
    )

    content = EncryptedTextField(
        verbose_name=_("Content"),
        help_text=_("Note content (encrypted, markdown supported)"),
    )

    note_type = models.CharField(
        max_length=20,
        choices=NoteType.choices,
        default=NoteType.NOTE,
        verbose_name=_("Type"),
    )

    class Meta:
        verbose_name = _("Client note")
        verbose_name_plural = _("Client notes")
        ordering = ["-note_date", "-created_at"]
        indexes = [
            models.Index(fields=["client", "note_date"], name="clientnote_client_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{_('Note')} {self.client.client_code} – {self.note_date}"
