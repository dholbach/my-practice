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

from ..fields import EncryptedCharField, EncryptedTextField
from .base import TimestampedModel
from .client import Client
from .session import Session

# ─── Preloaded template text ──────────────────────────────────────────────────
# Baked into form initial= values (not model defaults) so existing blank
# ClientProfile rows stay empty and only new forms get the boilerplate.

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
    SCHWER = "schwer", "Schwer"
    MITTEL = "mittel", "Mittel"
    LEICHT = "leicht", "Leicht"

    # Client state
    HOHE_AKTIVIERUNG = "hohe_aktivierung", "Hohe Aktivierung"
    GUTE_RESSOURCEN = "gute_ressourcen", "Gute Ressourcen"
    KRISE = "krise", "Krise"
    NIEDRIG_AFFEKTIV = "niedrig_affektiv", "Niedrig affektiv"
    DISSOZIATION = "dissoziation", "Dissoziation"
    UNSICHER = "unsicher", "Unsicher"

    # Format
    ONLINE = "online", "Online"

    # Progress
    FORTSCHRITT = "fortschritt", "Fortschritt"
    UPDATE_CHITCHAT = "update_chitchat", "Update / Chitchat"
    RUECKSCHRITT = "rueckschritt", "Rückschritt"
    DURCHBRUCH = "durchbruch", "Durchbruch"
    RICHTUNGSLOS = "richtungslos", "Richtungslos"


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
        verbose_name="Klient",
    )

    # Zone 1: intake assessment (rarely updated after intake)
    intake_notes = EncryptedTextField(
        blank=True,
        verbose_name="Aufnahme & Anamnese",
        help_text="Erstgespräch + klinische Bewertung (verschlüsselt)",
    )

    # Zone 2: evolving case formulation
    case_notes = EncryptedTextField(
        blank=True,
        verbose_name="Fallnotizen",
        help_text="Themen, Dynamik, Herausforderungen, Zukünftige Arbeit (verschlüsselt)",
    )

    # Quick-reference diagnosis label — visible on client page overview
    arbeitsdiagnose = EncryptedCharField(
        blank=True,
        verbose_name="Arbeitsdiagnose",
        help_text="Klinische Arbeitsdiagnose (verschlüsselt)",
    )

    class Meta:
        verbose_name = "Klientenprofil"
        verbose_name_plural = "Klientenprofile"

    def __str__(self) -> str:
        return f"Profil: {self.client.client_code}"


class SessionLog(TimestampedModel):
    """
    Per-session clinical reflection entry.

    Links to the central Session object. Metadata (session_type, mood_tags) is
    stored unencrypted so triage signals can be computed without the Fernet key.
    Narrative content (content, therapist_reflection) is Fernet-encrypted.
    """

    class SessionType(models.TextChoices):
        ERSTGESPRAECH = "erstgespraech", "Erstgespräch"
        STANDARD = "standard", "Standard"
        KRISENINTERVENTION = "krisenintervention", "Krisenintervention"
        ABSCHLUSSPHASE = "abschlussphase", "Abschlussphase"
        AUSFALL = "ausfall", "Ausfall / Absage"

    session = models.OneToOneField(
        Session,
        on_delete=models.CASCADE,
        related_name="log",
        verbose_name="Sitzung",
    )

    session_type = models.CharField(
        max_length=30,
        choices=SessionType.choices,
        default=SessionType.STANDARD,
        verbose_name="Sitzungstyp",
        # NOT encrypted — used for triage signals and basic UI labels
    )

    mood_tags = models.JSONField(
        default=list,
        verbose_name="Stimmungs-Tags",
        help_text="Auswahl aus vordefinierten Signalen (unverschlüsselt, für Triage)",
        # NOT encrypted — enables emergency triage summary without Fernet key
    )

    summary = models.CharField(
        max_length=120,
        blank=True,
        default="",
        verbose_name="Kurzzusammenfassung",
        help_text="Einzeiler für den Überblick (unverschlüsselt, max. 120 Zeichen)",
        # NOT encrypted — shown in Überblick cockpit without Fernet key
    )

    content = EncryptedTextField(
        blank=True,
        verbose_name="Sitzungsnotiz",
        help_text="Pre-filled: Gefühl danach / Wahrnehmung / Sitzung / Was half (verschlüsselt)",
    )

    interventions = EncryptedTextField(
        blank=True,
        verbose_name="Interventionen",
        help_text="Angewandte Techniken und Interventionen (verschlüsselt)",
    )

    therapist_reflection = EncryptedTextField(
        blank=True,
        verbose_name="Eigene Reflexion",
        help_text="Wie ging es mir dabei — Gegenübertragung (verschlüsselt, separat)",
    )

    class Meta:
        verbose_name = "Sitzungsprotokoll"
        verbose_name_plural = "Sitzungsprotokolle"
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
        OFFEN = "offen", "Offen"
        BESPROCHEN = "besprochen", "Besprochen"

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="supervision_items",
        verbose_name="Klient",
    )

    content = EncryptedTextField(
        verbose_name="Inhalt",
        help_text="Supervisionsfrage oder -thema (verschlüsselt)",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OFFEN,
        verbose_name="Status",
        # NOT encrypted — used for filtering open/closed items
    )

    class Meta:
        verbose_name = "Supervisionsthema"
        verbose_name_plural = "Supervisionsthemen"
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
        NOTE = "note", "Notiz"
        SUPERVISION = "supervision", "Supervision"

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="client_notes",
        verbose_name="Klient",
    )

    note_date = models.DateField(
        verbose_name="Datum",
        help_text="Datum des Eintrags (z.B. Anruf, Supervision, Notiz)",
    )

    content = EncryptedTextField(
        verbose_name="Inhalt",
        help_text="Notizinhalt (verschlüsselt, Markdown unterstützt)",
    )

    note_type = models.CharField(
        max_length=20,
        choices=NoteType.choices,
        default=NoteType.NOTE,
        verbose_name="Typ",
    )

    class Meta:
        verbose_name = "Klientennotiz"
        verbose_name_plural = "Klientennotizen"
        ordering = ["-note_date", "-created_at"]
        indexes = [
            models.Index(fields=["client", "note_date"], name="clientnote_client_date_idx"),
        ]

    def __str__(self) -> str:
        return f"Notiz {self.client.client_code} – {self.note_date}"
