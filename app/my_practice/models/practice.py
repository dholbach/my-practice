"""Practice/practitioner configuration model"""

from typing import Any

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Practice(models.Model):
    """
    Practice information for invoices and contact details.

    Supports multi-practice setups where one user can manage multiple
    separate businesses (e.g., Therapy Practice + Coaching Business).
    """

    # Users with access to this practice (via UserPractice M2M)
    users: models.ManyToManyField = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="UserPractice",
        related_name="practices",
        verbose_name="Benutzer",
    )

    name = models.CharField(max_length=200, default="", verbose_name="Praktiker Name")
    slug = models.SlugField(
        max_length=50,
        unique=True,
        default="default",
        verbose_name="URL-Slug",
        help_text="Eindeutiger Bezeichner für die Praxis (z.B. 'therapy', 'coaching')",
    )
    short_title = models.CharField(
        max_length=50,
        default="Therapie",
        verbose_name="Kurzbezeichnung",
        help_text="Kurze Bezeichnung für Titelzeile (z.B. 'Therapie', 'Coaching')",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv",
        help_text="Inaktive Praxen werden nicht angezeigt",
    )
    title = models.CharField(
        max_length=200,
        default="Heilpraktiker für Psychotherapie",
        verbose_name="Berufsbezeichnung",
    )
    subtitle_de = models.CharField(
        max_length=200,
        default="praxis für körperpsychotherapie",
        verbose_name="Untertitel (Deutsch)",
        blank=True,
    )
    subtitle_en = models.CharField(
        max_length=200,
        default="deutsch & english",
        verbose_name="Untertitel (English)",
        blank=True,
    )

    # Address
    street = models.CharField(max_length=200, default="")
    postal_code = models.CharField(max_length=10, default="")
    city = models.CharField(max_length=100, default="")
    country = models.CharField(max_length=100, default="Deutschland", blank=True)

    # Contact
    email = models.EmailField(default="")
    email_from_name = models.CharField(
        max_length=200,
        default="",
        verbose_name="E-Mail Absendername",
        help_text="Name displayed in 'From' field of outgoing emails",
    )
    website = models.URLField(default="")
    booking_url = models.URLField(
        default="",
        blank=True,
        verbose_name="Buchungs-URL",
        help_text="Link zur Online-Terminbuchung (z. B. Calendly). Wird automatisch in Anfrage-E-Mail-Vorlagen eingefügt.",
    )
    phone = models.CharField(max_length=50, blank=True)

    # Banking
    bank_name = models.CharField(max_length=200, default="")
    iban = models.CharField(max_length=34, default="")
    bic = models.CharField(max_length=11, default="")
    private_bank_account = models.CharField(
        max_length=34,
        blank=True,
        verbose_name="Privates Bankkonto (IBAN)",
        help_text="IBAN des privaten Kontos für automatische Erkennung von Entnahmen und Kapitaleinlagen beim Bank-Import",
    )

    # Tax
    tax_id = models.CharField(max_length=50, default="", verbose_name="Steuernummer")

    # VAT exemption: Choose between Kleinunternehmer (§19) vs. Heilpraktiker (§4 Nr.14)
    is_kleinunternehmer = models.BooleanField(
        default=False,
        verbose_name="Kleinunternehmer-Regelung",
        help_text="Wenn aktiviert: §19 UStG (Kleinunternehmer) statt §4 Nr.14 UStG (Heilpraktiker)",
    )
    kleinunternehmer_text_de = models.TextField(
        default="Der Betrag ist umsatzsteuerfrei nach § 19 UStG (Kleinunternehmerregelung).",
        verbose_name="Kleinunternehmer-Text (Deutsch)",
        help_text="Wird verwendet wenn 'Kleinunternehmer-Regelung' aktiviert ist",
    )
    kleinunternehmer_text_en = models.TextField(
        default="This amount is VAT-exempt according to § 19 UStG (small business regulation).",
        verbose_name="Kleinunternehmer-Text (English)",
        blank=True,
        help_text="Used when 'Kleinunternehmer-Regelung' is enabled",
    )

    vat_exempt_text_de = models.TextField(
        default="Der Betrag ist umsatzsteuerfrei nach § 4 Nr. 14 UStG",
        verbose_name="USt-Befreiungstext (Deutsch)",
        help_text="Wird verwendet wenn 'Kleinunternehmer-Regelung' NICHT aktiviert ist",
    )
    vat_exempt_text_en = models.TextField(
        default="This amount is exempt from VAT according to § 4 No. 14 UStG",
        verbose_name="USt-Befreiungstext (English)",
        help_text="Used when 'Kleinunternehmer-Regelung' is NOT enabled",
    )

    # Memberships
    memberships_de = models.TextField(
        default="",
        verbose_name="Mitgliedschaften (Deutsch)",
    )
    memberships_en = models.TextField(
        default="",
        verbose_name="Memberships (English)",
        blank=True,
    )

    # Images
    logo = models.ImageField(upload_to="practice/", blank=True, null=True, verbose_name="Logo")
    signature = models.ImageField(
        upload_to="practice/", blank=True, null=True, verbose_name="Unterschrift"
    )

    # Payment terms
    payment_terms_days = models.IntegerField(default=14, verbose_name="Zahlungsziel (Tage)")
    payment_terms_text_de = models.CharField(
        max_length=200,
        default="Bitte überweisen Sie den Rechnungsbetrag unter Angabe der Rechnungsnummer innerhalb von 14 Tagen auf das unten genannte Konto.",
        verbose_name="Zahlungsbedingungen (Deutsch)",
    )
    payment_terms_text_en = models.CharField(
        max_length=200,
        default="Please transfer the invoice amount stating the invoice number within 14 days to the account mentioned below.",
        verbose_name="Payment Terms (English)",
    )

    # Email templates for invoices
    invoice_email_subject_de = models.CharField(
        max_length=200,
        default="Rechnung {invoice_number}",
        verbose_name="Email Betreff (Deutsch)",
        help_text="Platzhalter: {invoice_number}, {amount}, {date}, {client_name}",
    )
    invoice_email_subject_en = models.CharField(
        max_length=200,
        default="Invoice {invoice_number}",
        verbose_name="E-Mail Betreff (English)",
        help_text="Placeholders: {invoice_number}, {amount}, {date}, {client_name}",
    )
    invoice_email_body_de = models.TextField(
        default="{salutation},\n\n{sessions_intro}anbei erhalten Sie die Rechnung {invoice_number} über {amount} vom {date}.\n\n"
        "Bitte überweisen Sie den Betrag innerhalb von 14 Tagen unter Angabe der Rechnungsnummer.\n\n"
        "Die Rechnung ist als PDF im Anhang beigefügt.",
        verbose_name="Email Text (Deutsch)",
        help_text="Platzhalter: {salutation}, {sessions_intro}, {invoice_number}, {amount}, {date}, {client_name}",
    )
    invoice_email_body_en = models.TextField(
        default="{salutation},\n\n{sessions_intro}Please find attached invoice {invoice_number} for {amount} dated {date}.\n\n"
        "Please transfer the amount within 14 days, stating the invoice number.\n\n"
        "The invoice is attached as a PDF.",
        verbose_name="E-Mail Text (English)",
        help_text="Placeholders: {salutation}, {sessions_intro}, {invoice_number}, {amount}, {date}, {client_name}",
    )
    email_signature = models.TextField(
        default="Mit freundlichen Grüßen / Best regards,\nHeilpraktiker für Psychotherapie",
        verbose_name="E-Mail Signatur",
        help_text="Used for all outgoing emails",
    )

    # Commute / Fahrtkosten (P-027)
    commute_distance_km = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Entfernung zur Praxis (km)",
        help_text="Einfache Strecke in km (z.B. 12). Wird für die Entfernungspauschale auf der Steuer-Jahresübersicht verwendet.",
    )
    practice_weekdays = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Praxistage (Wochentage)",
        help_text="Wochentage, an denen die Praxis besucht wird (0=Mo, 1=Di, 2=Mi, 3=Do, 4=Fr).",
    )

    # Capacity Monitoring (P-013 Phase 3)
    monthly_target_hours = models.DecimalField(
        max_digits=6,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="Monats-Ziel: Stunden",
        help_text="Ziel-Stunden (Sitzungen) pro Monat, z.B. 60.0. Aktiviert Kapazitäts-Monitoring im Dashboard.",
    )
    monthly_target_revenue = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Monats-Ziel: Umsatz (€)",
        help_text="Ziel-Umsatz pro Monat in €, z.B. 3000.00. Aktiviert Kapazitäts-Monitoring im Dashboard.",
    )

    class Meta:
        verbose_name = "Praxiseinstellungen"
        verbose_name_plural = "Praxiseinstellungen"

    def __str__(self) -> str:
        return f"{self.name} - {self.title}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Auto-generate slug from name if not set or still default"""
        if not self.slug or self.slug == "default":
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class UserPractice(models.Model):
    """
    Many-to-Many through table linking users to practices.

    Allows one user to manage multiple practices and tracks
    ownership/access rights per practice.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="practice_memberships",
        verbose_name="Benutzer",
    )
    practice = models.ForeignKey(
        Practice,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="Praxis",
    )
    is_owner = models.BooleanField(
        default=False,
        verbose_name="Eigentümer",
        help_text="Eigentümer haben volle Verwaltungsrechte",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")

    class Meta:
        verbose_name = "Benutzer-Praxis-Zuordnung"
        verbose_name_plural = "Benutzer-Praxis-Zuordnungen"
        unique_together = [["user", "practice"]]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        owner_str = " (Eigentümer)" if self.is_owner else ""
        return f"{self.user.username} → {self.practice.name}{owner_str}"
