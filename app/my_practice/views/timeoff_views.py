"""Time-off views: CRUD outside /admin, plus the heads-up email notice to clients."""

import logging

from django.contrib import messages
from django.core.mail import EmailMessage
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View

from ..email_forms import TimeOffNoticeForm
from ..forms import TimeOffForm
from ..models import Client, TimeOff
from ..utils.email_utils import (
    get_salutation_for_client,
    get_timeoff_notice_default_content,
    render_email_template,
)
from .crud_mixins import (
    NextRedirectMixin,
    PracticeScopedCreateView,
    PracticeScopedDeleteView,
    PracticeScopedUpdateView,
)
from .email_views import _make_from_email

logger = logging.getLogger("my_practice.email")


def timeoff_list(request: HttpRequest) -> HttpResponse:
    """List all time-off periods, split into upcoming/current and past."""
    all_timeoff = TimeOff.objects.all().order_by("start_date")
    upcoming = [t for t in all_timeoff if not t.is_past]
    past = sorted((t for t in all_timeoff if t.is_past), key=lambda t: t.start_date, reverse=True)

    return render(
        request,
        "my_practice/time_off_list.html",
        {"upcoming": upcoming, "past": past},
    )


class TimeOffCreateView(PracticeScopedCreateView):
    """Create a new time-off period"""

    model = TimeOff
    form_class = TimeOffForm
    template_name = "my_practice/time_off_form.html"
    success_url = reverse_lazy("timeoff_list")
    success_message = _("'{obj.title}' created successfully.")


class TimeOffUpdateView(NextRedirectMixin, PracticeScopedUpdateView):
    """Update an existing time-off period"""

    model = TimeOff
    form_class = TimeOffForm
    template_name = "my_practice/time_off_form.html"
    success_url = reverse_lazy("timeoff_list")
    success_message = _("'{obj.title}' updated successfully.")
    context_object_name = "time_off"


class TimeOffDeleteView(NextRedirectMixin, PracticeScopedDeleteView):
    """Delete a time-off period"""

    model = TimeOff
    template_name = "my_practice/time_off_confirm_delete.html"
    success_url = reverse_lazy("timeoff_list")
    context_object_name = "time_off"
    success_message = _("'{obj.title}' deleted successfully.")


class SendTimeOffNoticeView(View):
    """Send a heads-up email about one or more time-off periods to selected clients."""

    template_name = "my_practice/time_off_notice_form.html"

    def _get_time_offs(self, request: HttpRequest) -> list[TimeOff]:
        ids = request.GET.getlist("ids") or request.POST.getlist("ids")
        time_offs = list(TimeOff.objects.filter(pk__in=ids).order_by("start_date"))
        if not time_offs:
            raise Http404("No time-off periods selected.")
        return time_offs

    def get(self, request: HttpRequest) -> HttpResponse:
        time_offs = self._get_time_offs(request)
        practice = request.current_practice

        if not practice:
            messages.error(request, _("Practice settings not configured."))
            return redirect("timeoff_list")

        subject_de, body_de, subject_en, body_en = get_timeoff_notice_default_content(
            time_offs, practice
        )
        form = TimeOffNoticeForm(
            practice=practice,
            initial={
                "subject_de": subject_de,
                "body_de": body_de,
                "subject_en": subject_en,
                "body_en": body_en,
            },
        )
        # All recipients pre-checked by default (see form initial above) — the
        # template renders the recipient table by hand, so it needs the checked
        # set spelled out explicitly rather than relying on widget iteration.
        checked_ids = {
            str(pk) for pk in form.fields["recipients"].queryset.values_list("pk", flat=True)
        }
        return render(
            request,
            self.template_name,
            {"time_offs": time_offs, "form": form, "checked_ids": checked_ids},
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        time_offs = self._get_time_offs(request)
        practice = request.current_practice

        if not practice:
            messages.error(request, _("Practice settings not configured."))
            return redirect("timeoff_list")

        form = TimeOffNoticeForm(request.POST, practice=practice)
        if not form.is_valid():
            checked_ids = set(request.POST.getlist("recipients"))
            return render(
                request,
                self.template_name,
                {"time_offs": time_offs, "form": form, "checked_ids": checked_ids},
            )

        recipients: list[Client] = list(form.cleaned_data["recipients"])
        subject_de = form.cleaned_data["subject_de"]
        body_de = form.cleaned_data["body_de"]
        subject_en = form.cleaned_data["subject_en"]
        body_en = form.cleaned_data["body_en"]
        from_email = _make_from_email(practice)

        sent_count = 0
        failed_clients: list[str] = []
        for client in recipients:
            if client.language == "en":
                subject, body_template = subject_en, body_en
            else:
                subject, body_template = subject_de, body_de

            body = render_email_template(
                body_template, {"salutation": get_salutation_for_client(client)}
            )

            try:
                result = EmailMessage(
                    subject=subject, body=body, from_email=from_email, to=[client.email]
                ).send()
                if result == 1:
                    sent_count += 1
                else:
                    failed_clients.append(client.client_code)
            except Exception as e:
                logger.exception(f"Failed to send time-off notice to {client.client_code}: {e}")
                failed_clients.append(client.client_code)

        if sent_count:
            messages.success(
                request,
                _("Heads-up email sent to %(count)d of %(total)d clients.")
                % {"count": sent_count, "total": len(recipients)},
            )
        if failed_clients:
            messages.error(
                request,
                _("Failed to send to: %(clients)s") % {"clients": ", ".join(failed_clients)},
            )

        return redirect("timeoff_list")
