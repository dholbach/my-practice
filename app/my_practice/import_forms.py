"""
Forms for data import functionality.
"""

from django import forms

from .forms import StyledFormMixin


# Bank statement import forms


class BankStatementUploadForm(StyledFormMixin, forms.Form):
    """Form for uploading bank statement CSV files"""

    csv_file = forms.FileField(
        label="CSV-Datei",
        help_text="CSV-Kontoauszug im GLS-Bank-Format (Semikolon-getrennt, UTF-8). Andere Banken müssen ggf. das Format anpassen.",
        widget=forms.FileInput(attrs={"accept": ".csv"}),
    )

    skip_expenses = forms.BooleanField(
        label="Nicht-erkannte Ausgaben ignorieren",
        help_text="Überspringt negative Beträge, die nicht als Entnahme/Ausgabe erkannt werden. Entnahmen und Ausgaben werden automatisch erstellt.",
        initial=True,
        required=False,
    )

    def clean_csv_file(self):
        """Validate CSV file"""
        csv_file = self.cleaned_data["csv_file"]

        # Check file extension
        if not csv_file.name.endswith(".csv"):
            raise forms.ValidationError("Nur CSV-Dateien sind erlaubt.")

        # Check file size (max 5MB)
        if csv_file.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Datei ist zu groß (max. 5MB).")

        return csv_file


class TransactionMatchForm(StyledFormMixin, forms.Form):
    """Form for manually matching a transaction to one or more invoices"""

    invoice: forms.Field = forms.ModelMultipleChoiceField(
        queryset=None,  # Will be set in __init__
        label="Rechnung(en)",
        help_text="Eine oder mehrere Rechnungen der Zahlung zuordnen (für Sammelzahlungen)",
        required=False,  # Not required when ignoring
        widget=forms.SelectMultiple(attrs={"size": "10"}),
    )

    notes = forms.CharField(
        label="Notizen",
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
        help_text="Optionale Notizen zur manuellen Zuordnung",
    )

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Only show unpaid invoices from current practice
        if practice:
            from .models import Invoice

            self.fields["invoice"].queryset = (
                Invoice.objects.filter(
                    practice=practice,
                    status="sent",  # Only unpaid invoices
                )
                .select_related("client")
                .order_by("-invoice_date")
            )
            # Custom label format: <invoice code> (<invoice date>): <invoice amount>
            self.fields["invoice"].label_from_instance = self._invoice_label

    def _invoice_label(self, invoice):
        """Generate custom label for invoice dropdown"""
        total = invoice.calculate_total()
        # Format: XX-1 (2025-12-15): 90,00 €
        return f"{invoice.invoice_number} ({invoice.invoice_date}): {total:,.2f} €".replace(
            ",", " "
        )


class ExpenseGroupForm(StyledFormMixin, forms.Form):
    """Form for grouping bank transactions into a single expense"""

    from .models import CompanyExpense

    transactions: forms.Field = forms.ModelMultipleChoiceField(
        queryset=None,  # Will be set in __init__
        label="Transaktionen",
        widget=forms.CheckboxSelectMultiple,
        help_text="Wähle die Transaktionen, die zu einer Ausgabe zusammengefasst werden sollen",
    )

    category = forms.ChoiceField(
        choices=CompanyExpense.CATEGORY_CHOICES,
        label="Kategorie",
        initial="other",
    )

    description = forms.CharField(
        label="Beschreibung",
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
        help_text="Optional: Beschreibung für die zusammengefasste Ausgabe",
    )

    has_invoice = forms.BooleanField(
        label="Rechnung vorhanden",
        required=False,
        initial=False,
    )

    is_tax_deductible = forms.BooleanField(
        label="Steuerlich absetzbar",
        required=False,
        initial=True,
    )

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Only show negative bank transactions (potential expenses) that haven't been matched
        if practice:
            from .models import BankTransaction

            self.fields["transactions"].queryset = BankTransaction.objects.filter(
                practice=practice,
                amount__lt=0,  # Negative amounts
                match_confidence="unmatched",
                processed=False,
            ).order_by("-transaction_date")
