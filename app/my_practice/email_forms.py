"""
Forms for email sending.
"""

from datetime import date

from django import forms
from django.db.models import OuterRef, Subquery
from django.utils.translation import gettext_lazy as _

from .forms import StyledFormMixin
from .models import Client, Practice, Session


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


class TimeOffNoticeForm(StyledFormMixin, forms.Form):
    """Form for selecting recipients and customizing the time-off heads-up email.

    ``recipients.queryset`` is annotated with ``last_session_date``/``next_session_date``
    so the template can render a scannable table (code, language, last/next session)
    instead of a plain name list — the queryset is exposed as
    ``form.recipients.field.queryset`` for that purpose.
    """

    recipients = forms.ModelMultipleChoiceField(
        queryset=Client.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label=_("Recipients"),
    )
    subject_de = forms.CharField(label=_("Subject (German)"), max_length=200)
    body_de = forms.CharField(label=_("Message (German)"), widget=forms.Textarea(attrs={"rows": 8}))
    subject_en = forms.CharField(label=_("Subject (English)"), max_length=200)
    body_en = forms.CharField(
        label=_("Message (English)"), widget=forms.Textarea(attrs={"rows": 8})
    )

    def __init__(self, *args, practice: Practice, **kwargs):
        super().__init__(*args, **kwargs)
        today = date.today()
        # Separate, non-overlapping subqueries — a plain Max("sessions__session_date")
        # would return a future session as "last session" too, since it's just the
        # overall max regardless of whether it's in the past.
        last_session_subquery = (
            Session.objects.filter(client=OuterRef("pk"), session_date__lt=today, cancelled=False)
            .order_by("-session_date")
            .values("session_date")[:1]
        )
        next_session_subquery = (
            Session.objects.filter(client=OuterRef("pk"), session_date__gte=today, cancelled=False)
            .order_by("session_date")
            .values("session_date")[:1]
        )
        recipients_qs = (
            Client.objects.filter(practice=practice, active=True)
            .exclude(email="")
            .annotate(
                last_session_date=Subquery(last_session_subquery),
                next_session_date=Subquery(next_session_subquery),
            )
            .order_by("client_code")
        )
        self.fields["recipients"].queryset = recipients_qs
        if not self.is_bound:
            self.fields["recipients"].initial = recipients_qs
