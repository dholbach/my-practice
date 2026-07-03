"""
Client-related views.
"""

import logging
import os
from datetime import date, timedelta
from typing import cast

from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMessage
from django.db import models, transaction
from django.db.models import Max, QuerySet
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST

from ..forms import ClientIntakeForm
from ..models import Client, ClientDocument, ClientTag, Invoice
from ..utils.email_utils import get_gdpr_deletion_email_content
from ..utils.file_processing import process_upload
from ..utils import (
    RevenueCalculator,
    annotate_activity_status,
    sort_tags_by_category,
)
from ..utils.view_helpers import safe_next
from .crud_mixins import PracticeScopedListView, PracticeScopedUpdateView

logger = logging.getLogger(__name__)

GDPR_RETENTION_YEARS = 10


class ClientListView(PracticeScopedListView):
    """List all clients with workflow-focused card layout"""

    model = Client
    template_name = "my_practice/client_list_cards.html"
    context_object_name = "clients"
    paginate_by = 100  # Prevents slow renders; grouping works on per-page slice
    ordering = ["client_code"]

    def get_queryset(self) -> QuerySet[Client]:
        # Get practice-scoped queryset from parent
        queryset = cast(QuerySet[Client], super().get_queryset())

        # Advanced Search — PostgreSQL FTS for name/notes, icontains for code/email
        search_query = self.request.GET.get("search", "").strip()
        if search_query:
            name_vector = SearchVector("full_name", "notes", config="german")
            name_q = SearchQuery(search_query, config="german", search_type="plain")
            queryset = queryset.annotate(_name_rank=SearchRank(name_vector, name_q)).filter(
                models.Q(_name_rank__gt=0)
                | models.Q(client_code__icontains=search_query)
                | models.Q(email__icontains=search_query)
            )

        # Filter by tag
        tag_filter = self.request.GET.get("tag")
        if tag_filter:
            queryset = queryset.filter(tags__slug=tag_filter).distinct()

        # Prefetch tags for efficient display (prevents N+1 queries)
        queryset = queryset.prefetch_related("tags")

        queryset = queryset.annotate(
            last_session_date=models.Max("sessions__session_date"),
            total_revenue=RevenueCalculator.get_client_revenue_subquery(),
            total_sessions=RevenueCalculator.get_client_sessions_subquery(),
        )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        today = date.today()
        all_clients = list(context["clients"])
        annotate_activity_status(all_clients, today=today)

        # Use centralized grouping function from client_helpers
        from ..utils.client_helpers import group_clients_by_activity

        grouped = group_clients_by_activity(all_clients, use_attention_category=True)

        clients_needs_attention = grouped["needs_attention"]
        clients_active_ok = grouped["active_ok"]
        clients_inactive = grouped["inactive"]

        context["clients_needs_attention"] = clients_needs_attention
        context["clients_active_ok"] = clients_active_ok
        context["clients_inactive"] = clients_inactive

        clients_inactive_by_year: dict[int | str, list] = {}
        for client in clients_inactive:
            year = client.last_session_year if client.last_session_year else None

            if year not in clients_inactive_by_year:
                clients_inactive_by_year[year] = []
            clients_inactive_by_year[year].append(client)

        # Sort years descending (most recent first), with None (no sessions) last
        context["clients_inactive_by_year"] = dict(
            sorted(
                clients_inactive_by_year.items(),
                key=lambda x: (
                    x[0] is None,
                    -x[0] if isinstance(x[0], int) else 0,
                ),
            )
        )

        # Clients eligible for GDPR deletion (inactive + last session 10+ years ago)
        retention_cutoff = today - timedelta(days=365 * GDPR_RETENTION_YEARS + 2)
        clients_deletion_eligible = [
            c
            for c in clients_inactive
            if c.last_session_date and c.last_session_date <= retention_cutoff
        ]
        context["clients_deletion_eligible"] = clients_deletion_eligible

        # Stats for header
        context["stats"] = {
            "needs_attention": len(clients_needs_attention),
            "active_ok": len(clients_active_ok),
            "inactive": len(clients_inactive),
            "total": len(all_clients),
        }

        context["current_filter"] = self.request.GET.get("filter", "all")
        context["search_query"] = self.request.GET.get("search", "")
        context["current_tag"] = self.request.GET.get("tag", "")

        # Clients with past sessions that have no SessionLog yet — live query for the 📝 indicator.
        from ..models import Session
        from ..utils import SESSION_LOG_MIN_DURATION, SESSION_LOG_WINDOW_DAYS

        today_date = date.today()
        cutoff = today_date - timedelta(days=SESSION_LOG_WINDOW_DAYS)
        clients_needing_log = set(
            Session.objects.filter(
                client__practice=self.request.current_practice,
                log__isnull=True,
                cancelled=False,
                session_date__gte=cutoff,
                session_date__lt=today_date,
                duration__gt=SESSION_LOG_MIN_DURATION,
            ).values_list("client_id", flat=True)
        )
        context["clients_needing_log"] = clients_needing_log

        # Get all tags with client counts for filter UI
        # Sort by category priority (attention → general → exit), then alphabetically
        all_tags = ClientTag.objects.annotate(client_count=models.Count("clients"))
        context["all_tags"] = sort_tags_by_category(all_tags)

        return context


class ClientIntakeView(PracticeScopedUpdateView):
    """Client intake/edit form - supports both creating and updating clients"""

    model = Client
    form_class = ClientIntakeForm
    template_name = "my_practice/client_intake.html"
    success_url = reverse_lazy("client_list")
    success_message = _("Client {obj.full_name} saved successfully!")

    def get_success_url(self) -> str:
        return safe_next(self.request, fallback=str(self.success_url))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "")
        return context

    def get_object(self, queryset=None):
        """Get existing client if pk is provided, else return new instance"""
        # Check if we have a pk in URL kwargs (for /clients/<pk>/edit/)
        pk = self.kwargs.get("pk")

        if pk:
            # Edit mode: Load existing client
            if queryset is None:
                queryset = self.get_queryset()
            return get_object_or_404(queryset, pk=pk)

        # Check legacy client parameter (for ?client=ID style URLs)
        client_id = self.request.GET.get("client") or self.request.POST.get("client_id")
        if client_id and client_id != "None":
            if queryset is None:
                queryset = self.get_queryset()
            return get_object_or_404(queryset, pk=client_id)

        # Create mode: Return new instance
        return Client()

    def form_valid(self, form):
        """Save with practice assignment for new clients"""
        # Set practice if creating new client (no pk yet)
        if not form.instance.pk and not form.instance.practice_id:
            form.instance.practice = self.request.current_practice

        return super().form_valid(form)


def client_detail(request, pk):
    """Client detail view with invoice history and statistics."""
    from django.db.models import Prefetch

    from ..utils import ClientDetailContextBuilder

    client = get_object_or_404(
        Client.objects.for_current_practice(request).prefetch_related(
            Prefetch(
                "invoices",
                queryset=Invoice.objects.order_by("-invoice_date").prefetch_related("items"),
            ),
            "tags",
            Prefetch(
                "documents",
                queryset=ClientDocument.objects.order_by("-document_date", "-created_at"),
            ),
        ),
        pk=pk,
    )
    context = ClientDetailContextBuilder(client, request).build()
    return render(request, "my_practice/client_detail.html", context)


def client_onboarding_step(request, pk):
    """Mark or reset a single onboarding step for a client (POST only)."""
    from datetime import date

    from django.http import HttpResponseNotAllowed

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    client = get_object_or_404(Client.objects.for_current_practice(request), pk=pk)

    step = request.POST.get("step", "")
    reset = request.POST.get("reset") == "1"

    field_map = {
        "intake": "intake_sent_date",
        "contract": "contract_signed_date",
        "questionnaire": "questionnaire_sent_date",
        "complete": "onboarding_complete_date",
    }

    if step in field_map:
        setattr(client, field_map[step], None if reset else date.today())
        client.save(update_fields=[field_map[step]])

    if step == "complete" and not reset:
        tag = ClientTag.objects.filter(slug="incomplete-intake").first()
        if tag:
            client.tags.remove(tag)

    return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#ptab-profil")


@require_POST
def client_document_upload(request: HttpRequest, pk: int) -> JsonResponse:
    """Upload a document for a client. Returns JSON with document metadata.

    Side effect: if the document type maps to an onboarding step (intake,
    contract, anamnese) and that step is not yet marked complete, the
    corresponding Client date field is set to the document date.  The JSON
    response includes ``onboarding_step_completed`` (step name or null) so
    the caller can reload the page to reflect the updated sidebar.
    """
    from datetime import date as date_type
    from pathlib import Path

    client = get_object_or_404(Client.objects.for_current_practice(request), pk=pk)
    raw_file = request.FILES.get("file")
    if not raw_file:
        return JsonResponse({"error": str(_("No file selected."))}, status=400)
    try:
        doc_file = process_upload(raw_file)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    doc_type = request.POST.get("document_type", ClientDocument.DocumentType.OTHER)
    valid_types = {dt.value for dt in ClientDocument.DocumentType}
    if doc_type not in valid_types:
        doc_type = ClientDocument.DocumentType.OTHER

    description = request.POST.get("description", "")[:200]
    doc_date_str = request.POST.get("document_date", "")
    try:
        doc_date = date_type.fromisoformat(doc_date_str) if doc_date_str else date_type.today()
    except ValueError:
        doc_date = date_type.today()

    doc = ClientDocument.objects.create(
        client=client,
        document_type=doc_type,
        file=doc_file,
        description=description,
        document_date=doc_date,
    )

    onboarding_step_completed = None
    dt = ClientDocument.DocumentType
    onboarding_map = {
        dt.INTAKE: ("intake_sent_date", "intake"),
        dt.CONTRACT: ("contract_signed_date", "contract"),
        dt.ANAMNESE: ("questionnaire_sent_date", "anamnese"),
    }
    if doc_type in onboarding_map:
        field, step = onboarding_map[doc_type]
        if not getattr(client, field):
            setattr(client, field, doc_date)
            client.save(update_fields=[field])
            onboarding_step_completed = step

    return JsonResponse(
        {
            "id": doc.pk,
            "document_type": doc.document_type,
            "document_type_display": doc.get_document_type_display(),
            "description": doc.description,
            "document_date": str(doc.document_date),
            "filename": Path(doc.file.name or "").name,
            "url": doc.file.url,
            "onboarding_step_completed": onboarding_step_completed,
        },
        status=201,
    )


@require_POST
def client_document_delete(request: HttpRequest, pk: int) -> JsonResponse:
    """Delete a client document. Returns JSON."""
    doc = get_object_or_404(ClientDocument, pk=pk)
    if doc.client.practice != request.current_practice:
        raise PermissionDenied
    doc.file.delete(save=False)
    doc.delete()
    return JsonResponse({"success": True})


def _gdpr_cutoff() -> date:
    return date.today() - timedelta(days=365 * GDPR_RETENTION_YEARS + 2)


def client_gdpr_delete_confirm(request: HttpRequest, pk: int) -> HttpResponse:
    """Confirmation page before GDPR deletion of a client record."""

    client = get_object_or_404(Client.objects.for_current_practice(request), pk=pk)
    last_session = client.sessions.aggregate(last=Max("session_date"))["last"]

    if client.active or not last_session or last_session > _gdpr_cutoff():
        messages.error(
            request,
            _(
                "Client %(code)s does not meet the requirements for GDPR deletion "
                "(inactive + last session more than %(years)s years ago)."
            )
            % {"code": client.client_code, "years": GDPR_RETENTION_YEARS},
        )
        return redirect("client_list")

    return render(
        request,
        "my_practice/client_gdpr_delete_confirm.html",
        {
            "client": client,
            "last_session": last_session,
            "invoice_count": client.invoices.count(),
            "document_count": client.documents.count(),
            "has_email": bool(client.email),
        },
    )


@require_POST
def client_gdpr_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """GDPR Art. 17 deletion: send notification email then erase client data."""

    client = get_object_or_404(Client.objects.for_current_practice(request), pk=pk)
    last_session = client.sessions.aggregate(last=Max("session_date"))["last"]

    if client.active or not last_session or last_session > _gdpr_cutoff():
        messages.error(request, _("Requirements for GDPR deletion not met."))
        return redirect("client_list")

    practice = request.current_practice
    client_code = client.client_code

    # Send notification email before deletion (best-effort)
    if client.email and practice:
        try:
            subject, body = get_gdpr_deletion_email_content(client, practice)
            msg = EmailMessage(
                subject=subject,
                body=body,
                from_email=practice.email,
                to=[client.email],
            )
            msg.send()
            logger.info("GDPR deletion email sent for %s", client_code)
        except Exception:
            logger.exception("Failed to send GDPR deletion email for %s", client_code)
            messages.warning(
                request,
                _(
                    "Note: The notification email to %(email)s could not be sent. "
                    "Please inform the client manually."
                )
                % {"email": client.email},
            )

    # Collect document file paths before deletion
    doc_file_paths = []
    for doc in client.documents.all():
        if doc.file and doc.file.name:
            try:
                doc_file_paths.append(doc.file.path)
            except ValueError:
                pass

    # Delete in FK dependency order (PROTECT constraints first)
    with transaction.atomic():
        client.sessions.all().delete()  # cascades SessionLog
        client.invoices.all().delete()  # cascades InvoiceItem
        client.delete()  # cascades ClientDocument records, ClientProfile,
        # SupervisionItem, ClientNote, ClientAlias

    # Delete document files from disk after DB records are gone
    for path in doc_file_paths:
        try:
            os.unlink(path)
        except OSError:
            logger.warning("Could not delete media file after GDPR erasure: %s", path)

    messages.success(
        request,
        _("Client %(code)s has been deleted pursuant to GDPR Art. 17.") % {"code": client_code},
    )
    return redirect("client_list")


def _generate_code_candidates(full_name: str) -> list[str]:
    """
    Generate candidate client codes from a full name, in priority order.

    Returns uppercase 2- and 3-letter strings derived from initials,
    first-N-of-first-name, first-N-of-last-name, and combinations.
    Only alpha characters are considered; digits and punctuation are stripped.
    """
    parts = [p for p in full_name.upper().split() if any(c.isalpha() for c in p)]
    parts = ["".join(c for c in p if c.isalpha()) for p in parts]
    parts = [p for p in parts if p]
    if not parts:
        return []

    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""

    candidates: list[str] = []

    # 2-letter: initials, first-2-of-first, first-2-of-last
    if last:
        candidates.append(first[0] + last[0])
    if len(first) >= 2:
        candidates.append(first[:2])
    if len(last) >= 2:
        candidates.append(last[:2])

    # 3-letter combinations
    if last:
        if len(first) >= 2:
            candidates.append(first[:2] + last[0])
        if len(last) >= 2:
            candidates.append(first[0] + last[:2])
    if len(parts) >= 3:
        candidates.append("".join(p[0] for p in parts[:3]))
    if len(first) >= 3:
        candidates.append(first[:3])
    if len(last) >= 3:
        candidates.append(last[:3])

    # Deduplicate preserving order
    seen: set[str] = set()
    result: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


def suggest_client_code(request: HttpRequest) -> JsonResponse:
    """
    Return available client code suggestions for a given name.

    GET /clients/suggest-code/?name=Anna+Schmidt
    → {"suggestions": ["AS", "AN", "SC", "ANS", "ASC"]}

    Checks all existing client codes across all practices so the suggestions
    are globally unique (since calendar entries are not practice-scoped).
    """
    name = request.GET.get("name", "").strip()
    if not name:
        return JsonResponse({"suggestions": []})

    candidates = _generate_code_candidates(name)
    taken = set(Client.objects.values_list("client_code", flat=True))
    available = [c for c in candidates if c not in taken]
    return JsonResponse({"suggestions": available[:6]})
