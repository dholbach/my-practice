"""Views for client inquiry / lead tracking (P-031)."""

from datetime import timedelta
from itertools import groupby
from typing import cast

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import (
    Case,
    IntegerField,
    Value,
    When,
)
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views import View

from ..inquiry_forms import InquiryConvertForm, InquiryForm, MarketingPeriodForm
from ..models import (
    Client,
    ClientInquiry,
    InquiryStatus,
    MarketingPeriod,
)
from ..utils.inquiry_analytics import build_inquiry_analytics
from ..utils.inquiry_email_templates import STAGE_EMAIL_TEMPLATES
from .crud_mixins import (
    PracticeScopedCreateView,
    PracticeScopedDeleteView,
    PracticeScopedListView,
    PracticeScopedUpdateView,
)


def _interpolate_inquiry_template(template: dict, inquiry: ClientInquiry, practice) -> dict:
    """Return a copy of the template dict with runtime values substituted."""
    first_name = inquiry.full_name.split()[0] if inquiry.full_name else ""
    practitioner = practice.name or ""
    booking = practice.booking_url or "[Buchungs-URL]"
    booking_en = practice.booking_url or "[booking URL]"

    def _sub(text: str) -> str:
        return (
            text.replace("<..>", first_name)
            .replace("[Buchungs-URL]", booking)
            .replace("[booking URL]", booking_en)
            .replace("[Ihr Name]", practitioner)
            .replace("[Your name]", practitioner)
        )

    result = dict(template)
    if "body" in result:
        result["body"] = _sub(result["body"])
    if "body_en" in result:
        result["body_en"] = _sub(result["body_en"])
    return result


class InquiryListView(PracticeScopedListView):
    """List all inquiries for the current practice, with optional status/source filter."""

    model = ClientInquiry
    template_name = "my_practice/inquiry_list.html"
    context_object_name = "inquiries"

    def get_queryset(self):
        qs = super().get_queryset().select_related("converted_client")
        status = self.request.GET.get("status")
        source = self.request.GET.get("source")
        # Default: hide closed inquiries unless explicitly requested
        if not self.request.GET.get("show_closed") and not status:
            qs = qs.open()
        if status:
            qs = qs.filter(status=status)
        if source:
            qs = qs.filter(source=source)
        # Sort by pipeline stage, then newest first within each stage
        status_priority = Case(
            When(status=InquiryStatus.NEW, then=Value(0)),
            When(status=InquiryStatus.CONTACTED, then=Value(1)),
            When(status=InquiryStatus.INTRO_MEETING, then=Value(2)),
            When(status=InquiryStatus.WAITLIST, then=Value(3)),
            When(status=InquiryStatus.IN_INTAKE, then=Value(3)),
            When(status=InquiryStatus.CONVERTED, then=Value(4)),
            When(status=InquiryStatus.DECLINED, then=Value(5)),
            When(status=InquiryStatus.UNREACHABLE, then=Value(5)),
            When(status=InquiryStatus.NOT_SUITABLE, then=Value(5)),
            When(status=InquiryStatus.LAPSED, then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )
        return qs.annotate(status_priority=status_priority).order_by(
            "status_priority", "-created_at"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_filter"] = self.request.GET.get("status", "")
        context["source_filter"] = self.request.GET.get("source", "")
        context["show_closed"] = bool(self.request.GET.get("show_closed"))
        context["status_choices"] = ClientInquiry._meta.get_field("status").choices
        context["source_choices"] = ClientInquiry._meta.get_field("source").choices
        context["marketing_periods"] = MarketingPeriod.objects.filter(
            practice=self.request.current_practice
        ).order_by("-start_date")
        analytics = build_inquiry_analytics(
            ClientInquiry.objects.for_current_practice(self.request),
            practice=self.request.current_practice,
        )
        context["analytics"] = analytics
        context["closed_count"] = analytics["closed_count"]

        # Group inquiries by pipeline stage for the section-header layout.
        # Items are already ordered by status_priority then -created_at.
        thirty_days_ago = timezone.localdate() - timedelta(days=30)
        _group_labels = {
            0: _("New"),
            1: _("Contacted"),
            2: _("Intro meeting"),
            3: _("Waitlist / intake"),
            4: _("Onboarded"),
            5: _("Closed"),
        }
        inquiry_groups = []
        for priority, group_iter in groupby(
            list(context["inquiries"]), key=lambda x: x.status_priority
        ):
            items = list(group_iter)
            fresh = [i for i in items if i.updated_at.date() >= thirty_days_ago]
            stale = [i for i in items if i.updated_at.date() < thirty_days_ago]
            inquiry_groups.append(
                {
                    "label": _group_labels.get(priority, _("Other")),
                    "priority": priority,
                    "status": items[0].status if items else "",
                    "fresh": fresh,
                    "stale": stale,
                    "total": len(items),
                }
            )
        context["inquiry_groups"] = inquiry_groups
        return context


class InquiryCreateView(PracticeScopedCreateView):
    """Create a new inquiry."""

    model = ClientInquiry
    form_class = InquiryForm
    template_name = "my_practice/inquiry_form.html"
    success_url = reverse_lazy("inquiry_list")
    success_message = gettext_lazy("Inquiry from {obj.full_name} recorded.")


class InquiryUpdateView(PracticeScopedUpdateView):
    """Edit an existing inquiry."""

    model = ClientInquiry
    form_class = InquiryForm
    template_name = "my_practice/inquiry_form.html"
    success_url = reverse_lazy("inquiry_list")
    success_message = gettext_lazy("Inquiry from {obj.full_name} saved.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["show_convert_button"] = self.object.can_convert()
        context["current_status"] = self.object.status
        context["booking_url_missing"] = not bool(self.request.current_practice.booking_url)
        context["all_email_templates"] = [
            {
                "status": status,
                "label": t["label"],
                "subject": t.get("subject", ""),
                "body": t.get("body", ""),
                "subject_en": t.get("subject_en", ""),
                "body_en": t.get("body_en", ""),
            }
            for status, t in (
                (s, _interpolate_inquiry_template(tmpl, self.object, self.request.current_practice))
                for s, tmpl in STAGE_EMAIL_TEMPLATES.items()
            )
        ]
        return context


class InquiryDeleteView(PracticeScopedDeleteView):
    """Delete an inquiry."""

    model = ClientInquiry
    template_name = "my_practice/inquiry_confirm_delete.html"
    success_url = reverse_lazy("inquiry_list")
    context_object_name = "inquiry"
    success_message = gettext_lazy("Inquiry from {obj.full_name} deleted.")


class MarketingPeriodCreateView(PracticeScopedCreateView):
    """Create a new marketing period."""

    model = MarketingPeriod
    form_class = MarketingPeriodForm
    template_name = "my_practice/marketing_period_form.html"
    success_url = reverse_lazy("inquiry_list")
    success_message = gettext_lazy("Marketing period recorded.")


class MarketingPeriodUpdateView(PracticeScopedUpdateView):
    """Edit an existing marketing period."""

    model = MarketingPeriod
    form_class = MarketingPeriodForm
    template_name = "my_practice/marketing_period_form.html"
    success_url = reverse_lazy("inquiry_list")
    success_message = gettext_lazy("Marketing period saved.")


class MarketingPeriodDeleteView(PracticeScopedDeleteView):
    """Delete a marketing period."""

    model = MarketingPeriod
    template_name = "my_practice/marketing_period_confirm_delete.html"
    success_url = reverse_lazy("inquiry_list")
    context_object_name = "period"
    success_message = gettext_lazy("Marketing period deleted.")


class InquiryConvertView(LoginRequiredMixin, View):
    """
    Convert an inquiry to a Client.

    GET: Show confirmation form pre-filled with inquiry data.
    POST: Create the Client, link it to the inquiry, set status=CONVERTED.
    """

    def _get_inquiry(self, request: HttpRequest, pk: int) -> ClientInquiry:
        return cast(
            ClientInquiry,
            get_object_or_404(
                ClientInquiry.objects.for_current_practice(request),
                pk=pk,
            ),
        )

    def _refuse(self, request: HttpRequest, inquiry: ClientInquiry) -> HttpResponse:
        """Redirect away from an inquiry that can no longer be converted."""
        if inquiry.converted_client_id:
            messages.info(request, _("This inquiry has already been added as a client."))
            return redirect(reverse("client_detail", kwargs={"pk": inquiry.converted_client_id}))
        messages.error(request, _("This inquiry can no longer be added as a client."))
        return redirect(reverse("inquiry_list"))

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        inquiry = self._get_inquiry(request, pk)
        if not inquiry.can_convert():
            return self._refuse(request, inquiry)
        form = InquiryConvertForm()
        return render(
            request,
            "my_practice/inquiry_convert_confirm.html",
            {"inquiry": inquiry, "form": form},
        )

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        form = InquiryConvertForm(request.POST)
        with transaction.atomic():
            # The row lock serialises a double submit, so the second one sees the first's
            # client and is refused instead of creating a duplicate.
            inquiry = cast(
                ClientInquiry,
                get_object_or_404(
                    ClientInquiry.objects.for_current_practice(request).select_for_update(),
                    pk=pk,
                ),
            )
            if not inquiry.can_convert():
                return self._refuse(request, inquiry)

            if not form.is_valid():
                return render(
                    request,
                    "my_practice/inquiry_convert_confirm.html",
                    {"inquiry": inquiry, "form": form},
                )

            client = self._create_client(request, inquiry, form)

        messages.success(
            request,
            _("Client %(name)s (%(code)s) created successfully.")
            % {"name": client.full_name, "code": client.client_code},
        )
        return redirect(reverse("client_detail", kwargs={"pk": client.pk}))

    def _create_client(
        self, request: HttpRequest, inquiry: ClientInquiry, form: InquiryConvertForm
    ) -> Client:
        """Create the Client from the inquiry and mark the inquiry converted."""
        client = Client.objects.create(
            practice=request.current_practice,
            full_name=inquiry.full_name,
            email=inquiry.email,
            phone=inquiry.phone,
            client_code=form.cleaned_data["client_code"],
            first_seen_date=form.cleaned_data.get("first_seen_date"),
            hourly_rate_60=form.cleaned_data["default_hourly_rate"],
            hourly_rate_90=form.cleaned_data["default_hourly_rate"],
            language=inquiry.language,
        )

        inquiry.converted_client = client
        inquiry.status = InquiryStatus.CONVERTED
        if not inquiry.converted_date:
            inquiry.converted_date = timezone.localdate()
        inquiry.save(update_fields=["converted_client", "status", "converted_date", "updated_at"])
        return client
