"""
Additional forms for invoices.
"""

from decimal import Decimal
from typing import Any, cast

from django import forms
from django.forms import ModelChoiceField, inlineformset_factory
from django.utils import timezone
from django.utils.translation import gettext_lazy

from .forms import DateFormField, StyledFormMixin
from .models import Client, Invoice, InvoiceItem


class InvoiceForm(StyledFormMixin, forms.ModelForm):
    """Invoice creation/edit form with auto-generated invoice numbers and active client filtering."""

    # Override invoice_date to handle HTML5 date input properly
    invoice_date = DateFormField(
        label=gettext_lazy("Invoice date"),
    )

    # Override paid_date to handle HTML5 date input properly
    paid_date = DateFormField(
        required=False,
        label=gettext_lazy("Paid on"),
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
        ]
        widgets = {
            "client": forms.Select(attrs={"id": "id_client"}),
            "invoice_number": forms.TextInput(
                attrs={
                    "placeholder": gettext_lazy("Auto-generated (e.g., JL-5) or enter manually"),
                    "id": "id_invoice_number",
                }
            ),
            "status": forms.Select(),
            "tax_rate": forms.NumberInput(attrs={"step": "0.01", "value": "0.00"}),
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": gettext_lazy("Internal notes"),
                }
            ),
        }

    def __init__(self, *args: Any, request: Any, **kwargs: Any) -> None:
        """Initialize form with the current practice's clients and today's date for new invoices.

        ``request`` is required: the client choices come from its current practice,
        and a form built without one would have to guess (or offer every practice's clients).
        """
        self.request = request
        super().__init__(*args, **kwargs)

        practice_clients = Client.objects.for_current_practice(request)
        if self.instance.pk and self.instance.client:
            # Editing: every client of the practice, so a deactivated one stays selectable
            clients = practice_clients
        else:
            # Creating: active clients, plus an inactive one that is already chosen
            clients = practice_clients.filter(active=True)
            chosen = self._chosen_client(practice_clients)
            if chosen and not chosen.active:
                clients = clients | practice_clients.filter(pk=chosen.pk)
            cast(ModelChoiceField, self.fields["invoice_date"]).initial = timezone.localdate()
        cast(ModelChoiceField, self.fields["client"]).queryset = clients

    def _chosen_client(self, practice_clients: Any) -> Client | None:
        """The client preselected through ``initial`` or already submitted in the form data."""
        chosen = self.initial.get("client")
        if chosen or "client" not in self.data:
            return chosen
        try:
            return practice_clients.get(pk=self.data.get("client") or "")
        except Client.DoesNotExist, ValueError, TypeError:
            return None


class InvoiceItemForm(StyledFormMixin, forms.ModelForm):
    """
    Invoice item form for inline formset with default duration.

    A row is either session-linked (session_date + duration, the default) or
    free-form (description only, no session) — the latter only accepted when
    the current practice has Practice.allows_free_form_items set (P-122).
    """

    # Non-model fields: data goes to the linked Session, not to InvoiceItem directly.
    # Not required at the field level — a free-form row leaves these blank instead;
    # clean() enforces "session fields XOR description" per row.
    session_date = DateFormField(
        label=gettext_lazy("Session date"),
        required=False,
    )

    duration = forms.IntegerField(
        widget=forms.NumberInput(attrs={"min": "1", "value": "60"}),
        initial=60,
        label=gettext_lazy("Duration (minutes)"),
        required=False,
    )

    class Meta:
        model = InvoiceItem
        fields = [
            "service_type",
            "rate",
            "quantity",
            "description",
        ]
        widgets = {
            "service_type": forms.Select(attrs={"data-item-service": "true"}),
            "rate": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "data-item-rate": "true",
                }
            ),
            "quantity": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "description": forms.TextInput(
                attrs={"placeholder": gettext_lazy("Free-text line item — no linked session")}
            ),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize form with default values for new items."""
        # Extract request for practice-scoped queries
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Not required at the field level: existing forms/tests don't submit
        # it, matching the model's own default=1.00 (see clean()).
        self.fields["quantity"].required = False

        # Hide the free-form description/quantity fields entirely unless this
        # practice opted in — keeps the form honest even if a client tampers
        # with the POST data. Session items always bill at quantity 1;
        # quantity > 1 only makes sense for day-rate/project billing.
        practice = getattr(self.request, "current_practice", None) if self.request else None
        self.allows_free_form_items = bool(practice and practice.allows_free_form_items)
        if not self.allows_free_form_items:
            del self.fields["description"]
            del self.fields["quantity"]

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

            self.initial["session_date"] = timezone.localdate()

    def clean(self) -> dict[str, Any]:
        """Enforce "session_date XOR description" per row."""
        cleaned_data = super().clean()
        session_date = cleaned_data.get("session_date")
        description = cleaned_data.get("description") if self.allows_free_form_items else ""

        # Only touch cleaned_data["quantity"] when the field actually exists on
        # the form (allows_free_form_items) — otherwise construct_instance()
        # tries to look up the (deleted) field via form["quantity"] and raises
        # KeyError. When the field is absent, the model's own default (or the
        # existing instance value, on edit) applies untouched.
        if self.allows_free_form_items and cleaned_data.get("quantity") is None:
            cleaned_data["quantity"] = Decimal("1.00")

        if session_date and description:
            raise forms.ValidationError(
                gettext_lazy("Choose either a session date or a free-text description, not both.")
            )
        if not session_date and not description:
            raise forms.ValidationError(
                gettext_lazy("Enter either a session date or a free-text description.")
            )
        self._reject_session_to_free_form_conversion(session_date, description)
        if session_date and not cleaned_data.get("duration"):
            self.add_error("duration", gettext_lazy("Duration is required for a session item."))

        return cleaned_data

    def _reject_session_to_free_form_conversion(self, session_date, description) -> None:
        """Blanking session_date on a row that already has a linked Session
        would orphan that Session — no InvoiceItem would reference it anymore,
        so it starts showing up as "unbilled" even though it's already
        accounted for in this invoice's total. Deleting/detaching the Session
        automatically risks losing clinical documentation (SessionLog etc.)
        attached to it, so require an explicit new row instead of a silent
        conversion."""
        if self.instance.pk and self.instance.session_id and not session_date and description:
            raise forms.ValidationError(
                gettext_lazy(
                    "Converting a session-linked item to a free-form item isn't "
                    "supported — delete this item and add a new free-form item instead."
                )
            )


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
