"""
Generic CRUD mixins for reducing view code duplication.
"""

from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import ModelForm
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from ..utils.practice_helpers import is_practice_owner
from ..utils.view_helpers import safe_next


class PracticeOwnerRequiredMixin:
    """
    Restricts an Update/DeleteView to users who own the object's practice.

    Requires self.get_object() to return something usable directly as a
    Practice (or override permission_denied_practice() for other models).

    Example:
        class PracticeUpdateView(PracticeOwnerRequiredMixin, UpdateView):
            model = Practice
            permission_denied_message = _("You don't have permission to edit this practice.")
    """

    permission_denied_message: str | None = None
    permission_denied_redirect = "practice_management"

    def permission_denied_practice(self):
        """Return the Practice to check ownership against. Override if model != Practice."""
        return self.get_object()

    def dispatch(self, request, *args, **kwargs):
        practice = self.permission_denied_practice()
        if not is_practice_owner(request.user, practice):
            messages.error(request, self.permission_denied_message or _("Permission denied."))
            return redirect(self.permission_denied_redirect)
        return super().dispatch(request, *args, **kwargs)


class NextRedirectMixin:
    """
    Adds ?next= redirect support to an Update/DeleteView.

    get_success_url() honors ?next= (falling back to self.success_url), and
    the raw value is exposed to templates as context["next"] (e.g. for a
    Cancel link). Override get_success_url() in a subclass if the fallback
    needs to be something other than self.success_url.

    Example:
        class ExpenseDeleteView(NextRedirectMixin, PracticeScopedDeleteView):
            model = CompanyExpense
            success_url = reverse_lazy("expense_list")
    """

    def get_success_url(self) -> str:
        return safe_next(self.request, fallback=str(self.success_url))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "")
        return context


class InvoiceFormsetMixin:
    """
    Mixin for views that handle Invoice with InvoiceItemFormSet.

    Provides consistent formset handling for create/edit operations.
    Expects the view to have InvoiceItemFormSet imported.
    """

    def get_formset(self, invoice_instance=None):
        """
        Get InvoiceItemFormSet for current request.

        Args:
            invoice_instance: Invoice instance to bind formset to (None for create)

        Returns:
            InvoiceItemFormSet instance
        """
        from ..invoice_forms import get_invoice_item_formset

        if self.request.POST:
            formset = get_invoice_item_formset(
                request=self.request, data=self.request.POST, instance=invoice_instance
            )
        else:
            formset = get_invoice_item_formset(request=self.request, instance=invoice_instance)
        return formset

    def get_formset_context(
        self, context: dict[str, Any], formset_key: str = "items"
    ) -> dict[str, Any]:
        """
        Add formset to context dictionary.

        Args:
            context: Context dict to update
            formset_key: Key name for formset in context (default: "items")

        Returns:
            Updated context dict
        """
        # Get invoice instance from context if available (for edit views)
        invoice_instance = context.get("invoice") or context.get("object")
        context[formset_key] = self.get_formset(invoice_instance)
        return context


class PracticeScopedListView(LoginRequiredMixin, ListView):
    """
    Base ListView that automatically scopes queryset by current practice.

    Requires model to have PracticeScopedManager with .for_current_practice() method.

    Example:
        class ClientListView(PracticeScopedListView):
            model = Client
            template_name = "my_practice/client_list.html"
    """

    def get_queryset(self):
        """Get queryset scoped to current practice"""
        queryset = super().get_queryset()

        # Apply practice scoping via manager
        if hasattr(queryset, "for_current_practice"):
            queryset = queryset.for_current_practice(self.request)

        return queryset


class PracticeScopedCreateView(LoginRequiredMixin, CreateView):
    """
    Base CreateView that automatically assigns practice to new objects.

    Automatically sets practice field on save if model has one.
    Provides consistent success message handling.

    Example:
        class ClientCreateView(PracticeScopedCreateView):
            model = Client
            form_class = ClientForm
            template_name = "my_practice/client_form.html"
            success_url = reverse_lazy("client_list")
            success_message = "Client {obj.full_name} created successfully!"
    """

    success_message: str | None = None  # Override in subclass, supports .format(obj=instance)

    def form_valid(self, form: ModelForm) -> HttpResponse:
        """Save with practice assignment"""
        # Use practice_id (raw attname) rather than the FK descriptor, which raises
        # AttributeError for non-nullable FKs with a None value in Django 6+.
        if hasattr(form.instance, "practice_id") and form.instance.practice_id is None:
            form.instance.practice = self.request.current_practice

        response = super().form_valid(form)

        # Show success message if defined
        if self.success_message:
            msg = self.success_message.format(obj=self.object)
            messages.success(self.request, msg)

        return response


class PracticeScopedUpdateView(LoginRequiredMixin, UpdateView):
    """
    Base UpdateView that ensures objects are scoped to current practice.

    Automatically filters queryset by practice to prevent cross-practice access.
    Provides consistent success message handling.

    Example:
        class ClientUpdateView(PracticeScopedUpdateView):
            model = Client
            form_class = ClientForm
            template_name = "my_practice/client_form.html"
            success_url = reverse_lazy("client_list")
            success_message = "Client {obj.full_name} updated successfully!"
    """

    success_message: str | None = None  # Override in subclass, supports .format(obj=instance)
    context_object_name: str | None = None  # Override in subclass

    def get_queryset(self):
        """Get queryset scoped to current practice"""
        queryset = super().get_queryset()

        # Apply practice scoping via manager
        if hasattr(queryset, "for_current_practice"):
            queryset = queryset.for_current_practice(self.request)

        return queryset

    def form_valid(self, form: ModelForm) -> HttpResponse:
        """Save with success message"""
        response = super().form_valid(form)

        # Show success message if defined
        if self.success_message:
            msg = self.success_message.format(obj=self.object)
            messages.success(self.request, msg)

        return response


class PracticeScopedDeleteView(LoginRequiredMixin, DeleteView):
    """
    Base DeleteView scoped to current practice.

    Automatically filters queryset by practice to prevent cross-practice access.
    Provides consistent success message handling.

    Example:
        class ExpenseDeleteView(PracticeScopedDeleteView):
            model = CompanyExpense
            template_name = "my_practice/expense_confirm_delete.html"
            success_url = reverse_lazy("expense_list")
            context_object_name = "expense"
            success_message = "Ausgabe vom {obj.date:%d.%m.%Y} gelöscht."
    """

    success_message: str | None = None

    def get_queryset(self):
        """Get queryset scoped to current practice"""
        queryset = super().get_queryset()
        if hasattr(queryset, "for_current_practice"):
            queryset = queryset.for_current_practice(self.request)
        return queryset

    def form_valid(self, form: ModelForm) -> HttpResponse:
        """Delete with optional success message"""
        if self.success_message:
            msg = self.success_message.format(obj=self.object)
            messages.success(self.request, msg)
        return super().form_valid(form)
