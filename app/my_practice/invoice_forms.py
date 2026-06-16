"""
Additional forms for invoices.
"""

from datetime import date
from typing import Any, cast

from django import forms
from django.forms import ModelChoiceField, inlineformset_factory

from .forms import DateFormField, StyledFormMixin
from .models import Client, Invoice, InvoiceItem


class InvoiceForm(StyledFormMixin, forms.ModelForm):
    """Invoice creation/edit form with auto-generated invoice numbers and active client filtering."""

    # Override invoice_date to handle HTML5 date input properly
    invoice_date = DateFormField(
        label="Invoice Date / Rechnungsdatum",
    )

    # Override paid_date to handle HTML5 date input properly
    paid_date = DateFormField(
        required=False,
        label="Paid Date / Bezahlt am",
    )

    class Meta:
        model = Invoice
        fields = [
            "client",
            "invoice_number",
            "invoice_date",
            "paid_date",
            "status",
            "tax_rate",
            "notes",
            "practice",
        ]
        widgets = {
            "client": forms.Select(attrs={"id": "id_client"}),
            "invoice_number": forms.TextInput(
                attrs={
                    "placeholder": "Auto-generates if empty (e.g., XX-5)",
                    "id": "id_invoice_number",
                }
            ),
            "status": forms.Select(),
            "tax_rate": forms.NumberInput(attrs={"step": "0.01", "value": "0.00"}),
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Internal notes / Interne Notizen",
                }
            ),
        }
        labels = {
            "client": "Client / Klient",
            "invoice_number": "Invoice Number / Rechnungsnummer",
            "status": "Status",
            "tax_rate": "Tax Rate % / MwSt. %",
            "notes": "Notes / Notizen",
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize form with active clients and today's date for new invoices."""
        # Extract request for practice-scoped queries
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Show active clients, plus the current client if editing an existing invoice
        if self.instance.pk and self.instance.client:
            # Editing existing invoice - include all clients from current practice
            if self.request:
                cast(
                    ModelChoiceField, self.fields["client"]
                ).queryset = Client.objects.for_current_practice(self.request)
            else:
                cast(ModelChoiceField, self.fields["client"]).queryset = Client.objects.all()
        else:
            # Creating new invoice - show active clients from current practice
            if self.request:
                active_clients = Client.objects.for_current_practice(self.request).filter(
                    active=True
                )
            else:
                active_clients = Client.objects.filter(active=True)

            # Check both self.initial (from form kwargs) and form's initial data
            initial_client = self.initial.get("client")
            # Also check if client is already set in the form data
            if not initial_client and "client" in self.data:
                try:
                    initial_client = Client.objects.get(pk=self.data.get("client") or "")
                except Client.DoesNotExist, ValueError, TypeError:
                    initial_client = None

            if initial_client and not initial_client.active:
                # Include the inactive pre-selected client in the queryset
                cast(ModelChoiceField, self.fields["client"]).queryset = (
                    active_clients | Client.objects.filter(pk=initial_client.pk)
                )
            else:
                cast(ModelChoiceField, self.fields["client"]).queryset = active_clients
        # Set initial values if creating new
        if not self.instance.pk:
            cast(ModelChoiceField, self.fields["invoice_date"]).initial = date.today()


class InvoiceItemForm(StyledFormMixin, forms.ModelForm):
    """Invoice item form for inline formset with default duration."""

    # Non-model fields: data goes to the linked Session, not to InvoiceItem directly
    session_date = DateFormField(
        label="Sitzungsdatum",
    )

    duration = forms.IntegerField(
        widget=forms.NumberInput(attrs={"min": "1", "value": "60"}),
        initial=60,
        label="Dauer (Minuten)",
    )

    class Meta:
        model = InvoiceItem
        fields = [
            "service_type",
            "rate",
        ]
        widgets = {
            "service_type": forms.Select(attrs={"data-item-service": "true"}),
            "rate": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "data-item-rate": "true",
                }
            ),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize form with default values for new items."""
        # Extract request for practice-scoped queries
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Filter ServiceTypes by current practice + globals
        if self.request:
            from .models import ServiceType

            cast(
                ModelChoiceField, self.fields["service_type"]
            ).queryset = ServiceType.objects.for_current_practice_with_globals(self.request)

        # For existing items, pre-populate session_date and duration from linked session
        if self.instance.pk and self.instance.session_id:
            session = self.instance.session
            self.initial["session_date"] = session.session_date
            self.initial["duration"] = session.duration
        elif not self.instance.pk:
            # Set defaults for new items
            from .models import ServiceType

            # Try to find a default service type (therapy_60 or first available)
            if self.request:
                # Get first available service type for this practice
                default_service = ServiceType.objects.for_current_practice_with_globals(
                    self.request
                ).first()
            else:
                try:
                    default_service = ServiceType.objects.filter(code="therapy_60").first()
                except ServiceType.DoesNotExist:
                    default_service = None

            if default_service:
                cast(ModelChoiceField, self.fields["service_type"]).initial = default_service

            self.initial["session_date"] = date.today()


# Base formset for invoice items
_InvoiceItemFormSetBase = inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


def get_invoice_item_formset(request=None, **kwargs):
    """Factory function to create InvoiceItemFormSet with request context."""

    class InvoiceItemFormSet(_InvoiceItemFormSetBase):  # type: ignore[misc, valid-type]
        def _construct_form(self, i, **form_kwargs):
            """Override to pass request to each form."""
            if request:
                form_kwargs["request"] = request
            return super()._construct_form(i, **form_kwargs)

    return InvoiceItemFormSet(**kwargs)
