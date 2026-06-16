"""
Forms for email sending.
"""

from django import forms

from .forms import StyledFormMixin


class InvoiceEmailForm(StyledFormMixin, forms.Form):
    """Form for customizing invoice email content before sending."""

    recipient = forms.EmailField(
        label="To",
        widget=forms.EmailInput(),
    )
    subject = forms.CharField(
        label="Subject",
        max_length=200,
        widget=forms.TextInput(),
    )
    body = forms.CharField(
        label="Message",
        widget=forms.Textarea(attrs={"rows": 12}),
    )
