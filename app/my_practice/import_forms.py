"""
Forms for data import functionality.
"""

from django import forms
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from .forms import StyledFormMixin


# Bank statement import forms


class BankStatementUploadForm(StyledFormMixin, forms.Form):
    """Form for uploading bank statement CSV files"""

    csv_file = forms.FileField(
        label=gettext_lazy("CSV file"),
        help_text=gettext_lazy(
            "CSV bank statement matching your practice's configured CSV format "
            "(delimiter and column names, set under Practice settings). "
            "Defaults match GLS Bank's export."
        ),
        widget=forms.FileInput(attrs={"accept": ".csv"}),
    )

    skip_expenses = forms.BooleanField(
        label=gettext_lazy("Ignore unrecognized expenses"),
        help_text=gettext_lazy(
            "Skips negative amounts that aren't recognized as a withdrawal/expense. "
            "Withdrawals and expenses are created automatically."
        ),
        initial=True,
        required=False,
    )

    def clean_csv_file(self):
        """Validate CSV file"""
        csv_file = self.cleaned_data["csv_file"]

        # Check file extension
        if not csv_file.name.endswith(".csv"):
            raise forms.ValidationError(_("Only CSV files are allowed."))

        # Check file size (max 5MB)
        if csv_file.size > 5 * 1024 * 1024:
            raise forms.ValidationError(_("File is too large (max. 5MB)."))

        return csv_file


class TransactionMatchForm(StyledFormMixin, forms.Form):
    """Form for manually matching a transaction to one or more invoices"""

    invoice: forms.Field = forms.ModelMultipleChoiceField(
        queryset=None,  # Will be set in __init__
        label=gettext_lazy("Invoice(s)"),
        help_text=gettext_lazy(
            "Assign one or more invoices to the payment (for combined payments)"
        ),
        required=False,  # Not required when ignoring
        widget=forms.SelectMultiple(attrs={"size": "10"}),
    )

    notes = forms.CharField(
        label=gettext_lazy("Notes"),
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
        help_text=gettext_lazy("Optional notes for the manual match"),
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
        label=gettext_lazy("Transactions"),
        widget=forms.CheckboxSelectMultiple,
        help_text=gettext_lazy("Select the transactions to group into a single expense"),
    )

    category = forms.ChoiceField(
        choices=CompanyExpense.CATEGORY_CHOICES,
        label=gettext_lazy("Category"),
        initial="other",
    )

    description = forms.CharField(
        label=gettext_lazy("Description"),
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
        help_text=gettext_lazy("Optional: description for the grouped expense"),
    )

    has_invoice = forms.BooleanField(
        label=gettext_lazy("Invoice available"),
        required=False,
        initial=False,
    )

    is_tax_deductible = forms.BooleanField(
        label=gettext_lazy("Tax deductible"),
        required=False,
        initial=True,
    )

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Only show negative bank transactions (potential expenses) that haven't been matched
        if practice:
            from .models import BankTransaction

            self.fields["transactions"].queryset = (
                BankTransaction.objects.for_practice(practice)
                .filter(
                    amount__lt=0,  # Negative amounts
                    match_confidence="unmatched",
                    processed=False,
                )
                .order_by("-transaction_date")
            )
