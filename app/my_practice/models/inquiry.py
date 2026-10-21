"""Client inquiry / lead tracking model."""

from datetime import date
from enum import StrEnum

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ..fields import EncryptedTextField
from .base import PracticeScopedManager, PracticeScopedQuerySet, TimestampedModel


class InquirySource(StrEnum):
    """Channel through which the prospective client found the practice."""

    GOOGLE_ADS = "google_ads"
    GOOGLE_ORGANIC = "google_organic"
    WEBSITE = "website"
    REFERRAL = "referral"
    DIRECTORY = "directory"
    ITS_COMPLICATED = "its_complicated"
    NETWORK = "network"
    OTHER = "other"


INQUIRY_SOURCE_CHOICES = [
    (InquirySource.GOOGLE_ADS, "Google Ads"),
    (InquirySource.GOOGLE_ORGANIC, _("Google (organic)")),
    (InquirySource.WEBSITE, "Website"),
    (InquirySource.REFERRAL, _("Referral")),
    (InquirySource.DIRECTORY, _("Therapist directory")),
    (InquirySource.ITS_COMPLICATED, "It's Complicated"),
    (InquirySource.NETWORK, _("Network / colleagues")),
    (InquirySource.OTHER, _("Other")),
]


class InquiryStatus(StrEnum):
    """Pipeline stage for an incoming inquiry."""

    NEW = "new"
    CONTACTED = "contacted"
    INTRO_MEETING = "intro_meeting"
    WAITLIST = "waitlist"
    IN_INTAKE = "in_intake"
    CONVERTED = "converted"
    DECLINED = "declined"
    UNREACHABLE = "unreachable"
    NOT_SUITABLE = "not_suitable"
    LAPSED = "lapsed"


INQUIRY_STATUS_CHOICES = [
    (InquiryStatus.NEW, _("New")),
    (InquiryStatus.CONTACTED, _("Contacted")),
    (InquiryStatus.INTRO_MEETING, _("Intro meeting")),
    (InquiryStatus.WAITLIST, _("Waitlist")),
    (InquiryStatus.IN_INTAKE, _("Intake in progress")),
    (InquiryStatus.CONVERTED, _("Onboarded")),
    (InquiryStatus.DECLINED, _("Declined")),
    (InquiryStatus.UNREACHABLE, _("Unreachable")),
    (InquiryStatus.NOT_SUITABLE, _("Not a match")),
    (InquiryStatus.LAPSED, _("Lapsed")),
]

CLOSED_INQUIRY_STATUSES = frozenset(
    {
        InquiryStatus.CONVERTED,
        InquiryStatus.DECLINED,
        InquiryStatus.UNREACHABLE,
        InquiryStatus.NOT_SUITABLE,
        InquiryStatus.LAPSED,
    }
)

# An open inquiry with no new step for this long is closed as LAPSED: the
# outcome is unknown, so it gets its own status rather than a guessed one.
INQUIRY_LAPSE_DAYS = 60

# Closed inquiries that never became clients keep their personal data this long
# after the last contact, then are anonymised (GDPR Art. 5(1)(e)). There is no
# duty to retain a mere contact request; the statistical fields are kept.
INQUIRY_RETENTION_DAYS = 180


class ClientInquiryQuerySet(PracticeScopedQuerySet):
    """Custom QuerySet for ClientInquiry."""

    def open(self) -> "ClientInquiryQuerySet":
        """Return inquiries that are still in-progress (not closed)."""
        return self.exclude(status__in=CLOSED_INQUIRY_STATUSES)


INQUIRY_LANGUAGE_CHOICES = [
    ("de", _("German")),
    ("en", _("English")),
]


class ClientInquiry(TimestampedModel):
    """
    Tracks a prospective client from first contact through intake.

    Separate from Client — represents a lead before conversion.
    After conversion, links to the resulting Client via converted_client.
    """

    practice = models.ForeignKey(
        "Practice",
        on_delete=models.CASCADE,
        related_name="inquiries",
        verbose_name=_("Practice"),
    )
    full_name = models.CharField(max_length=200, verbose_name=_("Name"))
    email = models.EmailField(blank=True, verbose_name=_("Email"))
    phone = models.CharField(max_length=50, blank=True, verbose_name=_("Phone"))
    source = models.CharField(
        max_length=20,
        choices=INQUIRY_SOURCE_CHOICES,
        verbose_name=_("Source"),
    )
    status = models.CharField(
        max_length=20,
        choices=INQUIRY_STATUS_CHOICES,
        default=InquiryStatus.NEW,
        verbose_name=_("Status"),
    )
    inquiry_date = models.DateField(
        default=timezone.localdate,
        verbose_name=_("Date received"),
    )
    language = models.CharField(
        max_length=2,
        choices=INQUIRY_LANGUAGE_CHOICES,
        default="de",
        verbose_name=_("Language"),
        help_text=_("Preferred language of the person inquiring"),
    )
    # Encrypted: what someone says when first asking for therapy — their
    # concerns — is health data (Art. 9 GDPR) before they are even a client.
    notes = EncryptedTextField(blank=True, verbose_name=_("Notes"))
    initial_contact_notes = EncryptedTextField(
        blank=True,
        verbose_name=_("Initial contact notes"),
        help_text=_("Notes from the initial conversation (concerns, expectations, impressions)"),
    )

    # Milestone dates — each records when that pipeline stage was reached
    contacted_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Responded on"),
        help_text=_("Date of your first response / contact"),
    )
    intro_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Intro meeting on"),
        help_text=_("Date of the intro meeting"),
    )
    decision_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Decision on"),
        help_text=_("Date of the client decision (intake or decline / not a match)"),
    )
    converted_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Onboarded on"),
        help_text=_("Date of onboarding as a client"),
    )

    anonymised_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("Anonymised on"),
    )

    converted_client = models.OneToOneField(
        "Client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_inquiry",
        verbose_name=_("Client (after onboarding)"),
    )

    objects = PracticeScopedManager.from_queryset(ClientInquiryQuerySet)()

    class Meta:
        ordering = ["-inquiry_date", "-created_at"]
        verbose_name = _("Inquiry")
        verbose_name_plural = _("Inquiries")
        indexes = [
            models.Index(fields=["status"], name="inquiry_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.get_status_display()})"

    def is_closed(self) -> bool:
        """Return True if inquiry is in a terminal state."""
        return self.status in CLOSED_INQUIRY_STATUSES

    def last_step(self) -> tuple[date, str]:
        """Newest milestone reached, as (date, field name).

        A milestone may lie in the future (an intro meeting already booked).
        """
        fields = ("inquiry_date", "contacted_date", "intro_date", "decision_date")
        return max(
            ((getattr(self, field), field) for field in fields if getattr(self, field)),
            key=lambda pair: pair[0],
        )

    def anonymise(self) -> None:
        """Wipe everything that identifies the person; keep the statistical fields."""
        self.full_name = ""
        self.email = ""
        self.phone = ""
        self.notes = ""
        self.initial_contact_notes = ""
        self.anonymised_at = timezone.now()
        self.save(
            update_fields=[
                "full_name",
                "email",
                "phone",
                "notes",
                "initial_contact_notes",
                "anonymised_at",
                "updated_at",
            ]
        )


class MarketingPeriod(TimestampedModel):
    """
    Records a marketing channel or budget active during a given timeframe.

    Examples:
      - "Google Ads 5 €/Tag" from April to August 2026
      - "It's Complicated Premium" from January 2026 onwards

    Used to correlate inquiry sources with active spend / subscription periods.
    Future: show stats (leads per period, conversion rate) on the inquiry list.
    """

    practice = models.ForeignKey(
        "Practice",
        on_delete=models.CASCADE,
        related_name="marketing_periods",
        verbose_name=_("Practice"),
    )
    start_date = models.DateField(verbose_name=_("From"))
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("To"),
        help_text=_("Leave empty if still active"),
    )
    description = models.CharField(
        max_length=500,
        verbose_name=_("Description"),
        help_text=_('e.g. "Google Ads €5/day" or "It\'s Complicated Premium"'),
    )

    class Meta:
        ordering = ["-start_date"]
        verbose_name = _("Marketing period")
        verbose_name_plural = _("Marketing periods")

    def __str__(self) -> str:
        end = self.end_date.strftime("%m/%Y") if self.end_date else str(_("ongoing"))
        return f"{self.start_date.strftime('%m/%Y')}–{end}: {self.description}"

    def is_active(self) -> bool:
        """Return True if this period covers today."""
        today = timezone.localdate()
        return self.start_date <= today and (self.end_date is None or self.end_date >= today)
