"""
API views for the payments application.
"""

import logging
import zipfile
from io import BytesIO

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from weasyprint.text.fonts import FontConfiguration

from ..models import Client, Invoice
from ..utils import get_next_invoice_number
from ..utils.pdf_generation import (
    generate_contract_pdf_bytes,
    generate_intake_form_pdf_bytes,
    generate_questionnaire_pdf_bytes,
    prepare_practice_images,
    render_invoice_pdf_bytes,
)
from ..utils.practice_helpers import require_practice
from ..utils.questionnaire_content import QuestionnaireNotFoundError
from ..utils.view_helpers import is_partial_request, safe_next

logger = logging.getLogger(__name__)


def next_invoice_number(request: HttpRequest) -> JsonResponse:
    """API endpoint to get next invoice number for a client"""
    client_id = request.GET.get("client")
    if not client_id:
        return JsonResponse({"error": _("Client ID required")}, status=400)

    try:
        client = Client.objects.for_current_practice(request).get(pk=client_id)
        suggested_number = get_next_invoice_number(client)
        return JsonResponse({"suggested_number": suggested_number})
    except Client.DoesNotExist:
        return JsonResponse({"error": _("Client not found")}, status=404)


def invoice_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    """Generate and download PDF for a single invoice."""
    invoice = get_object_or_404(Invoice.objects.for_current_practice(request), pk=pk)
    practice = invoice.practice

    logo_data, signature_data = prepare_practice_images(practice)
    pdf_bytes, filename = render_invoice_pdf_bytes(invoice, practice, logo_data, signature_data)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def contract_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    """Generate pre-filled Behandlungsvertrag PDF for a client.

    Optional query param ``?lang=en`` switches to the English version;
    otherwise falls back to ``client.language``.
    """
    client = get_object_or_404(Client.objects.for_current_practice(request), pk=pk)
    practice = client.practice
    lang = request.GET.get("lang") or client.language or "de"
    pdf_bytes, filename = generate_contract_pdf_bytes(client, practice, lang)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def intake_form_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    """Generate pre-filled Aufnahmebogen (intake form) PDF for a client.

    Optional query param ``?lang=en`` switches to the English version;
    otherwise falls back to ``client.language``.
    """
    client = get_object_or_404(Client.objects.for_current_practice(request), pk=pk)
    practice = client.practice
    lang = request.GET.get("lang") or client.language or "de"
    pdf_bytes, filename = generate_intake_form_pdf_bytes(client, practice, lang)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@require_practice
def questionnaire_pdf(request: HttpRequest, code: str) -> HttpResponse:
    """Generate a blank, fillable clinical questionnaire PDF.

    Optional query param ``?lang=en`` switches to the English version
    (default: German).
    """
    practice = request.current_practice
    lang = request.GET.get("lang") or "de"
    try:
        pdf_bytes, filename = generate_questionnaire_pdf_bytes(code, practice, lang)
    except QuestionnaireNotFoundError as e:
        logger.warning("%s", e)
        messages.error(request, _("Questionnaire content file not found."))
        return redirect("dashboard")
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@require_POST
def invoice_batch_download(request: HttpRequest) -> HttpResponse:
    """
    Generate a ZIP archive of invoice PDFs for the given year and status.

    POST parameters:
        year   — 4-digit year (required)
        status — invoice status to filter by (default: "paid")
    """
    year_raw = request.POST.get("year", "").strip()
    status = request.POST.get("status", Invoice.Status.PAID)

    if not year_raw or not year_raw.isdigit():
        messages.error(request, _("Invalid year for batch download."))
        return HttpResponse(status=400)

    year = int(year_raw)

    # Deliberately not InvoiceFilterHelper: that filters paid invoices by paid_date__year
    # (M-PAT-02), but this endpoint archives by invoice_date year regardless of status.
    invoices = (
        Invoice.objects.for_current_practice(request)
        .filter(invoice_date__year=year, status=status)
        .select_related("client")
        .order_by("invoice_date", "invoice_number")
    )

    if not invoices.exists():
        messages.warning(
            request,
            _("No invoices found for %(year)s with status '%(status)s'.")
            % {"year": year, "status": status},
        )
        return HttpResponse(status=204)

    practice = request.current_practice
    logo_data, signature_data = prepare_practice_images(practice)

    # Share FontConfiguration across all renders to avoid repeated font loading from disk.
    font_config = FontConfiguration()

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for invoice in invoices:
            pdf_bytes, filename = render_invoice_pdf_bytes(
                invoice, practice, logo_data, signature_data, font_config
            )
            # Prefix client code for easy sorting: AB-1_Rechnung_AB-001.pdf
            entry_name = f"{invoice.client.client_code}_{filename}"
            zf.writestr(entry_name, pdf_bytes)

    zip_buffer.seek(0)
    zip_filename = f"Rechnungen_{year}.zip"
    response = HttpResponse(zip_buffer.read(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{zip_filename}"'
    return response


def update_invoice_status(request, pk):
    """Update invoice status via POST"""
    if request.method != "POST":
        return JsonResponse({"error": _("POST required")}, status=405)

    invoice = get_object_or_404(Invoice.objects.for_current_practice(request), pk=pk)
    new_status = request.POST.get("status")

    valid_statuses = {
        Invoice.Status.DRAFT,
        Invoice.Status.SENT,
        Invoice.Status.PAID,
        Invoice.Status.CANCELLED,
        Invoice.Status.WRITTEN_OFF,
    }
    if new_status not in valid_statuses:
        return JsonResponse({"error": _("Invalid status")}, status=400)
    if invoice.is_locked and new_status == Invoice.Status.DRAFT:
        return JsonResponse(
            {
                "error": _(
                    "An issued invoice cannot be set back to draft. "
                    "Cancel it and create a corrected copy instead."
                )
            },
            status=400,
        )

    if new_status == Invoice.Status.PAID:
        invoice.mark_paid()
    else:
        # A paid date only belongs to a paid invoice
        invoice.status = new_status
        invoice.paid_date = None
        invoice.save()

    # Partial request: return just the badge HTML for #invoice-status-{pk}
    if is_partial_request(request):
        badge_html = render_to_string(
            "includes/invoice_status_badge.html",
            {"invoice": invoice},
            request=request,
        )
        return HttpResponse(badge_html)

    messages.success(
        request,
        _("Status changed to: %(status)s") % {"status": invoice.get_status_display()},
    )

    next_url = safe_next(request, fallback="")
    if next_url:
        return redirect(next_url)

    return JsonResponse(
        {
            "status": new_status,
            "display": invoice.get_status_display(),
            "paid_date": (invoice.paid_date.strftime("%d.%m.%Y") if invoice.paid_date else None),
        }
    )
