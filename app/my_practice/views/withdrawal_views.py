"""Withdrawal views for the payments application.
Handles company withdrawal tracking and reporting.
"""

from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse_lazy

from ..forms import CompanyWithdrawalForm
from ..models import CompanyWithdrawal
from ..utils.financial_list_context_builder import FinancialListContextBuilder
from ..utils.view_helpers import get_year_from_request
from .crud_mixins import (
    NextRedirectMixin,
    PracticeScopedCreateView,
    PracticeScopedDeleteView,
    PracticeScopedUpdateView,
)


def withdrawal_list(request: HttpRequest) -> HttpResponse:
    """List all company withdrawals with yearly/monthly summaries"""

    # Get year filter from request
    year_filter = get_year_from_request(request, "year", None)

    all_qs = CompanyWithdrawal.objects.for_current_practice(request)

    # Build stat cards (grand_total, yearly_totals) from outgoing-only so that    # Kapitaleinlagen (stored as positive amounts) don't inflate the totals.
    outgoing_qs = all_qs.filter(category__in=CompanyWithdrawal.OUTGOING_CATEGORIES)
    builder = FinancialListContextBuilder(outgoing_qs, year_filter=year_filter)
    context, outgoing = builder.build_context(include_monthly=True)

    # Incoming / adjustments come from the full queryset with the same year filter
    incoming_qs = all_qs.filter(category__in=CompanyWithdrawal.INCOMING_CATEGORIES)
    if year_filter:
        incoming_qs = incoming_qs.filter(date__year=year_filter)
    incoming = incoming_qs.order_by("-date")

    outgoing_total = outgoing.aggregate(t=Sum("amount"))["t"] or 0
    # Contributions (Kapitaleinlagen) are stored as positive amounts but represent
    # money flowing INTO the business, so they offset corrections in the net total.
    corrections_total = incoming.filter(category="correction").aggregate(t=Sum("amount"))["t"] or 0
    contributions_total = (
        incoming.filter(category="contribution").aggregate(t=Sum("amount"))["t"] or 0
    )
    incoming_total = corrections_total - contributions_total

    context.update(
        {
            "outgoing": outgoing,
            "incoming": incoming,
            "outgoing_total": outgoing_total,
            "incoming_total": incoming_total,
            "current_year": year_filter or "all",
        }
    )

    return render(request, "my_practice/withdrawal_list.html", context)


class WithdrawalCreateView(PracticeScopedCreateView):
    """Create a new withdrawal"""

    model = CompanyWithdrawal
    form_class = CompanyWithdrawalForm
    template_name = "my_practice/withdrawal_form.html"
    success_url = reverse_lazy("withdrawal_list")
    success_message = "Entnahme vom {obj.date:%d.%m.%Y} erfolgreich erstellt."

    def get_initial(self):
        """Pre-fill category from ?category= query param (e.g. ?category=tax)."""
        initial = super().get_initial()
        category = self.request.GET.get("category")
        valid_categories = {c[0] for c in CompanyWithdrawal.CATEGORY_CHOICES}
        if category and category in valid_categories:
            initial["category"] = category
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action"] = "Erstellen"
        return context


class WithdrawalUpdateView(NextRedirectMixin, PracticeScopedUpdateView):
    """Update an existing withdrawal"""

    model = CompanyWithdrawal
    form_class = CompanyWithdrawalForm
    template_name = "my_practice/withdrawal_form.html"
    success_url = reverse_lazy("withdrawal_list")
    success_message = "Entnahme vom {obj.date:%d.%m.%Y} erfolgreich aktualisiert."
    context_object_name = "withdrawal"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action"] = "Bearbeiten"
        return context


class WithdrawalDeleteView(NextRedirectMixin, PracticeScopedDeleteView):
    """Delete a withdrawal"""

    model = CompanyWithdrawal
    template_name = "my_practice/withdrawal_confirm_delete.html"
    success_url = reverse_lazy("withdrawal_list")
    context_object_name = "withdrawal"
    success_message = "Entnahme vom {obj.date:%d.%m.%Y} über {obj.amount}€ erfolgreich gelöscht."
