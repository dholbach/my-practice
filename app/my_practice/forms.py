"""
Forms for the payments application.
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import CapacityPeriod, Client, CompanyExpense, CompanyWithdrawal, Practice, TimeOff


class DateFormField(forms.DateField):
    """DateField with standard HTML5 date input — use in ModelForm declarations."""

    def __init__(self, **kwargs):
        kwargs.setdefault("widget", forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
        kwargs.setdefault("input_formats", ["%Y-%m-%d"])
        super().__init__(**kwargs)


class StyledFormMixin:
    """
    Auto-applies CSS classes to all form widgets.

    Eliminates the need for attrs={"class": "form-control"} in every widget
    definition. CheckboxInput gets 'form-check-input'; everything else gets
    'form-control'.

    Usage:
        class MyForm(StyledFormMixin, forms.ModelForm):
            class Meta:
                model = MyModel
                fields = [...]
                widgets = {
                    # Only specify non-class attrs (type, step, rows, placeholder…)
                    "amount": forms.NumberInput(attrs={"step": "0.01"}),
                }
    """

    WIDGET_CLASSES: dict[type, str] = {
        forms.CheckboxInput: "form-check-input",
        forms.CheckboxSelectMultiple: "form-check-input",
    }
    DEFAULT_CLASS = "form-control"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = self.WIDGET_CLASSES.get(type(field.widget), self.DEFAULT_CLASS)
            existing = field.widget.attrs.get("class", "")
            if css not in existing:
                field.widget.attrs["class"] = f"{existing} {css}".strip()


class ClientIntakeForm(StyledFormMixin, forms.ModelForm):
    """Client intake form"""

    date_of_birth = DateFormField(required=False, label=_("Date of birth"))

    class Meta:
        model = Client
        fields = [
            "client_code",
            "full_name",
            "date_of_birth",
            "email",
            "phone",
            "address",
            "cost_carrier",
            "language",
            "salutation",
            "active",
            "is_online_client",
            "needs_gebueh_invoice",
            "hourly_rate_60",
            "hourly_rate_90",
            "notes",
        ]
        widgets = {
            "client_code": forms.TextInput(attrs={"placeholder": _("e.g. DE, JM"), "maxlength": 3}),
            "full_name": forms.TextInput(attrs={"placeholder": _("Full name")}),
            "email": forms.EmailInput(attrs={"placeholder": "email@example.com"}),
            "phone": forms.TextInput(attrs={"placeholder": "+49 ..."}),
            "address": forms.Textarea(
                attrs={"rows": 3, "placeholder": _("Street, postal code city")}
            ),
            "cost_carrier": forms.TextInput(
                attrs={"placeholder": _("e.g. self-pay, Allianz PKV, Beihilfe")}
            ),
            "salutation": forms.TextInput(
                attrs={"placeholder": 'e.g., "Dear John" or "Liebe Maria"'}
            ),
            "hourly_rate_60": forms.NumberInput(attrs={"step": "0.01"}),
            "hourly_rate_90": forms.NumberInput(attrs={"step": "0.01"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": _("Additional notes")}),
        }
        labels = {
            "client_code": _("Client code"),
            "full_name": _("Full name"),
            "email": _("Email"),
            "phone": _("Phone"),
            "address": _("Address"),
            "cost_carrier": _("Cost carrier"),
            "language": _("Preferred language"),
            "salutation": _("Custom Email Salutation"),
            "active": _("Active client"),
            "is_online_client": _("Online client (video sessions)"),
            "needs_gebueh_invoice": _("GebüH-Abrechnung"),
            "hourly_rate_60": _("Fee 60 min (€)"),
            "hourly_rate_90": _("Fee 90 min (€)"),
            "notes": _("Notes"),
        }


class CompanyWithdrawalForm(StyledFormMixin, forms.ModelForm):
    """Form for creating and editing company withdrawals"""

    date = DateFormField(label=_("Date"))

    class Meta:
        model = CompanyWithdrawal
        fields = ["date", "amount", "category", "description"]
        widgets = {
            "amount": forms.NumberInput(attrs={"step": "0.01", "placeholder": "0.00"}),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": _("Optional: purpose or notes"),
                }
            ),
        }
        labels = {
            "amount": _("Amount (€)"),
            "category": _("Category"),
            "description": _("Description"),
        }


class CompanyExpenseForm(StyledFormMixin, forms.ModelForm):
    """Form for creating and editing company expenses"""

    date = DateFormField(label=_("Date"))

    class Meta:
        model = CompanyExpense
        fields = [
            "date",
            "description",
            "category",
            "amount",
            "is_tax_deductible",
            "has_invoice",
            "is_filed_in_tax_return",
        ]
        widgets = {
            "description": forms.Textarea(
                attrs={"rows": 3, "placeholder": _("Description of the expense")}
            ),
            "amount": forms.NumberInput(attrs={"step": "0.01", "placeholder": "0.00"}),
            "receipt": forms.ClearableFileInput(attrs={"accept": "application/pdf,image/*"}),
        }
        labels = {
            "description": _("Description"),
            "category": _("Category"),
            "amount": _("Amount (€)"),
            "is_tax_deductible": _("Tax deductible"),
            "has_invoice": _("Invoice available"),
            "is_filed_in_tax_return": _("Filed in tax return"),
        }


class TimeOffForm(StyledFormMixin, forms.ModelForm):
    """Form for creating and editing time-off periods"""

    start_date = DateFormField(label=_("Start Date"))
    end_date = DateFormField(label=_("End Date"))

    class Meta:
        model = TimeOff
        fields = ["start_date", "end_date", "type", "title", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "type": _("Type"),
            "title": _("Title"),
            "notes": _("Notes"),
        }


_WEEKDAY_CHOICES = [
    (0, _("Monday")),
    (1, _("Tuesday")),
    (2, _("Wednesday")),
    (3, _("Thursday")),
    (4, _("Friday")),
]


class PracticeEditForm(StyledFormMixin, forms.ModelForm):
    """Practice update form with a friendly weekday multi-select for Fahrtkosten."""

    practice_weekdays = forms.MultipleChoiceField(
        choices=_WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_("Practice days (weekdays)"),
        help_text=_("Weekdays on which you commute to the practice."),
    )

    class Meta:
        model = Practice
        fields = [
            "name",
            "short_title_de",
            "short_title_en",
            "title",
            "subtitle_de",
            "subtitle_en",
            "street",
            "postal_code",
            "city",
            "country",
            "email",
            "email_from_name",
            "website",
            "booking_url",
            "phone",
            "bank_name",
            "iban",
            "bic",
            "tax_id",
            "is_kleinunternehmer",
            "kleinunternehmer_text_de",
            "kleinunternehmer_text_en",
            "vat_exempt_text_de",
            "vat_exempt_text_en",
            "logo",
            "signature",
            "memberships_de",
            "memberships_en",
            "payment_terms_days",
            "payment_terms_text_de",
            "payment_terms_text_en",
            "is_active",
            "commute_distance_km",
            "practice_weekdays",
        ]
        widgets = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate checkboxes from the JSONField list stored as ints
        instance = kwargs.get("instance")
        if instance and instance.practice_weekdays:
            self.fields["practice_weekdays"].initial = [str(d) for d in instance.practice_weekdays]

    def clean_practice_weekdays(self) -> list[int]:
        return [int(v) for v in self.cleaned_data.get("practice_weekdays") or []]


class CapacityPeriodForm(StyledFormMixin, forms.ModelForm):
    start_date = DateFormField(label=_("Valid from"))

    class Meta:
        model = CapacityPeriod
        fields = ["start_date", "hours_per_week"]


CapacityPeriodFormSet = forms.inlineformset_factory(
    Practice,
    CapacityPeriod,
    form=CapacityPeriodForm,
    extra=1,
    can_delete=True,
)
