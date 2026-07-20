"""Forms for client inquiry / lead tracking."""

from datetime import date
from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from .forms import DateFormField, StyledFormMixin
from .models import Client, ClientInquiry, InquiryStatus, MarketingPeriod


class InquiryForm(StyledFormMixin, forms.ModelForm):
    """Form for creating and editing a ClientInquiry."""

    inquiry_date = DateFormField(label=_("Date received"), initial=date.today)

    # Milestone dates — all optional; auto-filled when status reaches the corresponding stage
    contacted_date = DateFormField(label=_("Responded on"), required=False)
    intro_date = DateFormField(label=_("Intro meeting on"), required=False)
    decision_date = DateFormField(label=_("Decision on"), required=False)
    converted_date = DateFormField(label=_("Onboarded on"), required=False)

    class Meta:
        model = ClientInquiry
        fields = [
            "full_name",
            "email",
            "phone",
            "source",
            "language",
            "status",
            "inquiry_date",
            "contacted_date",
            "intro_date",
            "decision_date",
            "converted_date",
            "notes",
            "initial_contact_notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
            "initial_contact_notes": forms.Textarea(attrs={"rows": 5}),
        }

    def save(self, commit: bool = True) -> Any:
        """Auto-fill milestone dates when status reaches the corresponding stage."""
        instance = super().save(commit=False)
        today = date.today()
        status = instance.status
        if status == InquiryStatus.CONTACTED and not instance.contacted_date:
            instance.contacted_date = today
        if status == InquiryStatus.INTRO_MEETING and not instance.intro_date:
            instance.intro_date = today
        # Decision date: client said yes (IN_INTAKE) or any closing outcome
        _decision_statuses = {
            InquiryStatus.IN_INTAKE,
            InquiryStatus.DECLINED,
            InquiryStatus.NOT_SUITABLE,
            InquiryStatus.UNREACHABLE,
        }
        if status in _decision_statuses and not instance.decision_date:
            instance.decision_date = today
        if commit:
            instance.save()
        return instance


class InquiryConvertForm(StyledFormMixin, forms.Form):
    """
    Minimal form for converting an inquiry to a Client.

    Name/email/phone are displayed read-only in the template (from the inquiry).
    Only the fields needed to create the Client record are collected here.
    """

    client_code = forms.CharField(
        max_length=10,
        label=_("Client code"),
        help_text=_("Unique code, e.g. AB-1"),
    )
    first_seen_date = DateFormField(
        label=_("First appointment"),
        required=False,
    )
    default_hourly_rate = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        label=_("Hourly rate (€)"),
        widget=forms.NumberInput(attrs={"step": "0.01"}),
    )

    def clean_client_code(self) -> str:
        code = self.cleaned_data["client_code"].strip().upper()
        if Client.objects.filter(client_code=code).exists():
            raise forms.ValidationError(_('Code "%(code)s" is already taken.') % {"code": code})
        return str(code)


class MarketingPeriodForm(StyledFormMixin, forms.ModelForm):
    """Form for creating and editing a MarketingPeriod."""

    start_date = DateFormField(label=_("From"))
    end_date = DateFormField(label=_("To"), required=False)

    class Meta:
        model = MarketingPeriod
        fields = ["description", "start_date", "end_date"]
        widgets = {
            "description": forms.TextInput(attrs={"placeholder": _('e.g. "Google Ads €5/day"')}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", _("The end date must be after the start date."))
        return cleaned
