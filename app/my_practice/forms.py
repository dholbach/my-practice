"""
Forms for the payments application.
"""

from django import forms

from .models import CapacityPeriod, Client, CompanyExpense, CompanyWithdrawal, Practice


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

    date_of_birth = DateFormField(required=False, label="Geburtsdatum")

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
            "client_code": forms.TextInput(attrs={"placeholder": "z.B. DE, JM", "maxlength": 3}),
            "full_name": forms.TextInput(attrs={"placeholder": "Vollständiger Name"}),
            "email": forms.EmailInput(attrs={"placeholder": "email@example.com"}),
            "phone": forms.TextInput(attrs={"placeholder": "+49 ..."}),
            "address": forms.Textarea(attrs={"rows": 3, "placeholder": "Straße, PLZ Ort"}),
            "cost_carrier": forms.TextInput(
                attrs={"placeholder": "z.B. Selbstzahler, Allianz PKV, Beihilfe"}
            ),
            "salutation": forms.TextInput(
                attrs={"placeholder": 'e.g., "Dear John" or "Liebe Maria"'}
            ),
            "hourly_rate_60": forms.NumberInput(attrs={"step": "0.01"}),
            "hourly_rate_90": forms.NumberInput(attrs={"step": "0.01"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Zusätzliche Notizen"}),
        }
        labels = {
            "client_code": "Klienten-Code",
            "full_name": "Vollständiger Name",
            "email": "Email",
            "phone": "Telefon",
            "address": "Adresse",
            "cost_carrier": "Kostenträger",
            "language": "Bevorzugte Sprache",
            "salutation": "Custom Email Salutation",
            "active": "Aktiver Klient",
            "is_online_client": "Online-Klient (Videositzungen)",
            "needs_gebueh_invoice": "GebüH-Abrechnung",
            "hourly_rate_60": "Honorar 60 Min (€)",
            "hourly_rate_90": "Honorar 90 Min (€)",
            "notes": "Notizen",
        }


class CompanyWithdrawalForm(StyledFormMixin, forms.ModelForm):
    """Form for creating and editing company withdrawals"""

    date = DateFormField(label="Datum")

    class Meta:
        model = CompanyWithdrawal
        fields = ["date", "amount", "category", "description"]
        widgets = {
            "amount": forms.NumberInput(attrs={"step": "0.01", "placeholder": "0.00"}),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Optional: Verwendungszweck oder Notizen",
                }
            ),
        }
        labels = {
            "amount": "Betrag (€)",
            "category": "Kategorie",
            "description": "Beschreibung",
        }


class CompanyExpenseForm(StyledFormMixin, forms.ModelForm):
    """Form for creating and editing company expenses"""

    date = DateFormField(label="Datum")

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
                attrs={"rows": 3, "placeholder": "Beschreibung der Ausgabe"}
            ),
            "amount": forms.NumberInput(attrs={"step": "0.01", "placeholder": "0.00"}),
            "receipt": forms.ClearableFileInput(attrs={"accept": "application/pdf,image/*"}),
        }
        labels = {
            "description": "Beschreibung",
            "category": "Kategorie",
            "amount": "Betrag (€)",
            "is_tax_deductible": "Steuerlich absetzbar",
            "has_invoice": "Rechnung vorhanden",
            "is_filed_in_tax_return": "In Steuererklärung eingetragen",
        }


_WEEKDAY_CHOICES = [
    (0, "Montag"),
    (1, "Dienstag"),
    (2, "Mittwoch"),
    (3, "Donnerstag"),
    (4, "Freitag"),
]


class PracticeEditForm(StyledFormMixin, forms.ModelForm):
    """Practice update form with a friendly weekday multi-select for Fahrtkosten."""

    practice_weekdays = forms.MultipleChoiceField(
        choices=_WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Praxistage (Wochentage)",
        help_text="Wochentage, an denen Sie zur Praxis fahren.",
    )

    class Meta:
        model = Practice
        fields = [
            "name",
            "short_title",
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
    start_date = DateFormField(label="Gültig ab")

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
