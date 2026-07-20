"""Practice/practitioner configuration model"""

from typing import Any

from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


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
        verbose_name=_("Users"),
    )

    name = models.CharField(max_length=200, default="", verbose_name=_("Practitioner name"))
    slug = models.SlugField(
        max_length=50,
        unique=True,
        default="default",
        verbose_name=_("URL slug"),
        help_text=_("Unique identifier for the practice (e.g. 'therapy', 'coaching')"),
    )
    short_title = models.CharField(
        max_length=50,
        default="Therapie",
        verbose_name=_("Short title"),
        help_text=_("Short label for the title bar (e.g. 'Therapy', 'Coaching')"),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        help_text=_("Inactive practices are not shown"),
    )
    title = models.CharField(
        max_length=200,
        default="Heilpraktiker für Psychotherapie",
        verbose_name=_("Professional title"),
    )
    subtitle_de = models.CharField(
        max_length=200,
        default="praxis für körperpsychotherapie",
        verbose_name=_("Subtitle (German)"),
        blank=True,
    )
    subtitle_en = models.CharField(
        max_length=200,
        default="deutsch & english",
        verbose_name=_("Subtitle (English)"),
        blank=True,
    )

    # Address
    street = models.CharField(max_length=200, default="")
    postal_code = models.CharField(max_length=20, default="")
    city = models.CharField(max_length=100, default="")
    country = models.CharField(max_length=100, default="Deutschland", blank=True)

    # Contact
    email = models.EmailField(default="")
    email_from_name = models.CharField(
        max_length=200,
        default="",
        verbose_name=_("Email sender name"),
        help_text=_("Name displayed in 'From' field of outgoing emails"),
    )
    website = models.URLField(default="")
    booking_url = models.URLField(
        default="",
        blank=True,
        verbose_name=_("Booking URL"),
        help_text=_(
            "Link to online appointment booking (e.g. Calendly). "
            "Automatically inserted into inquiry email templates."
        ),
    )
    phone = models.CharField(max_length=50, blank=True)

    # Banking
    bank_name = models.CharField(max_length=200, default="")
    iban = models.CharField(max_length=34, default="")
    bic = models.CharField(max_length=11, default="")
    private_bank_account = models.CharField(
        max_length=34,
        blank=True,
        verbose_name=_("Private bank account (IBAN)"),
        help_text=_(
            "IBAN of the private account, for automatic detection of withdrawals "
            "and capital contributions during bank import"
        ),
    )

    # Tax
    tax_id = models.CharField(max_length=50, default="", verbose_name=_("Tax ID"))

    # VAT exemption: Choose between Kleinunternehmer (§19) vs. Heilpraktiker (§4 Nr.14)
    is_kleinunternehmer = models.BooleanField(
        default=False,
        verbose_name=_("Kleinunternehmer regulation"),
        help_text=_(
            "When enabled: § 19 UStG (small business) instead of § 4 No. 14 UStG (Heilpraktiker)"
        ),
    )
    kleinunternehmer_text_de = models.TextField(
        default="Der Betrag ist umsatzsteuerfrei nach § 19 UStG (Kleinunternehmerregelung).",
        verbose_name=_("Kleinunternehmer text (German)"),
        help_text=_("Used when 'Kleinunternehmer regulation' is enabled"),
    )
    kleinunternehmer_text_en = models.TextField(
        default="This amount is VAT-exempt according to § 19 UStG (small business regulation).",
        verbose_name=_("Kleinunternehmer text (English)"),
        blank=True,
        help_text=_("Used when 'Kleinunternehmer regulation' is enabled"),
    )

    vat_exempt_text_de = models.TextField(
        default="Der Betrag ist umsatzsteuerfrei nach § 4 Nr. 14 UStG",
        verbose_name=_("VAT exemption text (German)"),
        help_text=_("Used when 'Kleinunternehmer regulation' is NOT enabled"),
    )
    vat_exempt_text_en = models.TextField(
        default="This amount is exempt from VAT according to § 4 No. 14 UStG",
        verbose_name=_("VAT exemption text (English)"),
        help_text=_("Used when 'Kleinunternehmer regulation' is NOT enabled"),
    )

    # Memberships
    memberships_de = models.TextField(
        default="",
        verbose_name=_("Memberships (German)"),
    )
    memberships_en = models.TextField(
        default="",
        verbose_name=_("Memberships (English)"),
        blank=True,
    )

    # Images
    logo = models.ImageField(upload_to="practice/", blank=True, null=True, verbose_name=_("Logo"))
    signature = models.ImageField(
        upload_to="practice/", blank=True, null=True, verbose_name=_("Signature")
    )

    # Payment terms
    payment_terms_days = models.IntegerField(default=14, verbose_name=_("Payment term (days)"))
    payment_terms_text_de = models.CharField(
        max_length=200,
        default="Bitte überweisen Sie den Rechnungsbetrag unter Angabe der Rechnungsnummer innerhalb von 14 Tagen auf das unten genannte Konto.",
        verbose_name=_("Payment terms (German)"),
    )
    payment_terms_text_en = models.CharField(
        max_length=200,
        default="Please transfer the invoice amount stating the invoice number within 14 days to the account mentioned below.",
        verbose_name=_("Payment terms (English)"),
    )

    # Email templates for invoices
    invoice_email_subject_de = models.CharField(
        max_length=200,
        default="Rechnung {invoice_number}",
        verbose_name=_("Email subject (German)"),
        help_text=_("Placeholders: {invoice_number}, {amount}, {date}, {client_name}"),
    )
    invoice_email_subject_en = models.CharField(
        max_length=200,
        default="Invoice {invoice_number}",
        verbose_name=_("Email subject (English)"),
        help_text=_("Placeholders: {invoice_number}, {amount}, {date}, {client_name}"),
    )
    invoice_email_body_de = models.TextField(
        default="{salutation},\n\n{sessions_intro}anbei erhalten Sie die Rechnung {invoice_number} über {amount} vom {date}.\n\n"
        "Bitte überweisen Sie den Betrag innerhalb von 14 Tagen unter Angabe der Rechnungsnummer.\n\n"
        "Die Rechnung ist als PDF im Anhang beigefügt.",
        verbose_name=_("Email body (German)"),
        help_text=_(
            "Placeholders: {salutation}, {sessions_intro}, {invoice_number}, {amount}, {date}, {client_name}"
        ),
    )
    invoice_email_body_en = models.TextField(
        default="{salutation},\n\n{sessions_intro}Please find attached invoice {invoice_number} for {amount} dated {date}.\n\n"
        "Please transfer the amount within 14 days, stating the invoice number.\n\n"
        "The invoice is attached as a PDF.",
        verbose_name=_("Email body (English)"),
        help_text=_(
            "Placeholders: {salutation}, {sessions_intro}, {invoice_number}, {amount}, {date}, {client_name}"
        ),
    )
    email_signature = models.TextField(
        default="Mit freundlichen Grüßen / Best regards,\nHeilpraktiker für Psychotherapie",
        verbose_name=_("Email signature"),
        help_text=_("Used for all outgoing emails"),
    )

    # Commute / Fahrtkosten (P-027)
    commute_distance_km = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Distance to practice (km)"),
        help_text=_(
            "One-way distance in km (e.g. 12). Used for the distance allowance "
            "on the tax year summary."
        ),
    )
    practice_weekdays = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Practice days (weekdays)"),
        help_text=_(
            "Weekdays on which the practice is attended (0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri)."
        ),
    )

    # Capacity Monitoring (P-013 Phase 3)
    monthly_target_hours = models.DecimalField(
        max_digits=6,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name=_("Monthly target: hours"),
        help_text=_(
            "Target hours (sessions) per month, e.g. 60.0. Enables capacity "
            "monitoring on the dashboard."
        ),
    )
    monthly_target_revenue = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Monthly target: revenue (€)"),
        help_text=_(
            "Target revenue per month in €, e.g. 3000.00. Enables capacity "
            "monitoring on the dashboard."
        ),
    )

    class Meta:
        verbose_name = _("Practice settings")
        verbose_name_plural = _("Practice settings")

    def __str__(self) -> str:
        return f"{self.name} - {self.title}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Auto-generate slug from name if not set or still default"""
        if not self.slug or self.slug == "default":
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class CapacityPeriod(models.Model):
    """
    Defines available therapy hours per week for a given practice, from a start date onward.

    Periods are ordered by start_date. Each period is in effect from its start_date
    until the next period's start_date (or indefinitely if it is the last one).
    """

    practice = models.ForeignKey(
        Practice,
        on_delete=models.CASCADE,
        related_name="capacity_periods",
        verbose_name=_("Practice"),
    )
    start_date = models.DateField(verbose_name=_("Valid from"))
    hours_per_week = models.PositiveSmallIntegerField(
        verbose_name=_("Hours/week"),
        help_text=_("Available therapy hours per week from this date"),
    )

    class Meta:
        verbose_name = _("Capacity period")
        verbose_name_plural = _("Capacity periods")
        ordering = ["start_date"]
        unique_together = [["practice", "start_date"]]

    def __str__(self) -> str:
        return f"{self.start_date}: {self.hours_per_week}h/{_('week')}"


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
        verbose_name=_("User"),
    )
    practice = models.ForeignKey(
        Practice,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("Practice"),
    )
    is_owner = models.BooleanField(
        default=False,
        verbose_name=_("Owner"),
        help_text=_("Owners have full administrative rights"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created on"))

    class Meta:
        verbose_name = _("User-practice assignment")
        verbose_name_plural = _("User-practice assignments")
        unique_together = [["user", "practice"]]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        owner_str = f" ({_('Owner')})" if self.is_owner else ""
        return f"{self.user.username} → {self.practice.name}{owner_str}"
