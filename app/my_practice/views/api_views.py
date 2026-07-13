"""
API views for the payments application.
"""

import base64
import os
import zipfile
from datetime import date
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from PIL import Image
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration

from ..models import Client, Invoice, Practice
from ..utils import get_next_invoice_number
from ..utils.contract_form import add_contract_form_fields
from ..utils.gebueh_helpers import build_gebueh_blocks, gebueh_total_for_blocks, get_arbeitsdiagnose
from ..utils.practice_helpers import require_practice
from ..utils.questionnaire_content import QuestionnaireNotFoundError, load_questionnaire


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


# ---------------------------------------------------------------------------
# PDF helpers (shared between single-invoice and batch download)
# ---------------------------------------------------------------------------


def _prepare_practice_images(
    practice: Practice,
) -> tuple[str | None, str | None]:
    """
    Load and optimise practice logo and signature images.

    Returns:
        (logo_data, signature_data) as base64-encoded JPEG strings, or None
        if the image is missing.
    """
    logo_data: str | None = None
    signature_data: str | None = None

    for attr, max_size in (
        ("logo", (400, 160)),
        ("signature", (400, 160)),
    ):
        field = getattr(practice, attr, None)
        if not (field and os.path.exists(field.path)):
            continue
        img: Image.Image = Image.open(field.path)
        if img.mode in ("RGBA", "LA", "P"):
            # Composite onto paper background so transparent areas render
            # correctly in the PDF (plain convert("RGB") fills with black).
            bg = Image.new("RGBA", img.size, (251, 250, 246, 255))
            img = Image.alpha_composite(bg, img.convert("RGBA")).convert("RGB")
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        if attr == "logo":
            logo_data = encoded
        else:
            signature_data = encoded

    return logo_data, signature_data


def _render_invoice_pdf_bytes(
    invoice: Invoice,
    practice: Practice,
    logo_data: str | None,
    signature_data: str | None,
    font_config: FontConfiguration | None = None,
) -> tuple[bytes, str]:
    """
    Render a single invoice as a PDF in memory.

    Args:
        font_config: Optional shared FontConfiguration for batch rendering.
            Sharing one instance across multiple calls avoids repeated font
            loading from disk and speeds up batch PDF generation.

    Returns:
        (pdf_bytes, filename) where filename is suitable for download/zip entry.
    """
    if invoice.client.language == "de":
        template_name = "my_practice/invoice_pdf_de.html"
        filename = f"Rechnung_{invoice.invoice_number}.pdf"
    else:
        template_name = "my_practice/invoice_pdf_en.html"
        filename = f"Invoice_{invoice.invoice_number}.pdf"

    ctx: dict = {
        "invoice": invoice,
        "practice": practice,
        "logo_data": logo_data,
        "signature_data": signature_data,
    }

    if invoice.client.needs_gebueh_invoice:
        ctx["gebueh_blocks"] = build_gebueh_blocks(invoice)
        ctx["gebueh_total"] = gebueh_total_for_blocks(ctx["gebueh_blocks"])
        ctx["arbeitsdiagnose"] = get_arbeitsdiagnose(invoice.client)

    html_string = render_to_string(template_name, ctx)
    # base_url lets WeasyPrint resolve static font files (fonts/ dir) relative to the app
    base_url = f"file://{settings.BASE_DIR}/static/"
    pdf_bytes = HTML(string=html_string, base_url=base_url).write_pdf(font_config=font_config)
    return pdf_bytes, filename


def invoice_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    """Generate and download PDF for a single invoice."""
    invoice = get_object_or_404(Invoice.objects.for_current_practice(request), pk=pk)
    practice = invoice.practice

    logo_data, signature_data = _prepare_practice_images(practice)
    pdf_bytes, filename = _render_invoice_pdf_bytes(invoice, practice, logo_data, signature_data)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def generate_contract_pdf_bytes(client: Client, practice: Practice, lang: str) -> tuple[bytes, str]:
    """Render the pre-filled Behandlungsvertrag as PDF bytes.

    Returns:
        (pdf_bytes, filename) — filename is suitable for download or attachment.
    """
    logo_data, _signature = _prepare_practice_images(practice)
    html_string = render_to_string(
        "my_practice/treatment_contract_pdf.html",
        {"client": client, "practice": practice, "logo_data": logo_data, "lang": lang},
    )
    pdf_bytes = HTML(string=html_string).write_pdf()
    pdf_bytes = add_contract_form_fields(pdf_bytes)
    safe_code = client.client_code.replace("/", "-")
    filename = (
        f"Behandlungsvertrag_{safe_code}.pdf"
        if lang == "de"
        else f"TreatmentContract_{safe_code}.pdf"
    )
    return pdf_bytes, filename


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


def generate_intake_form_pdf_bytes(
    client: Client, practice: Practice, lang: str
) -> tuple[bytes, str]:
    """Render the pre-filled Aufnahmebogen as PDF bytes with fillable form fields.

    Returns:
        (pdf_bytes, filename) — filename is suitable for download or attachment.
    """
    logo_data, _signature = _prepare_practice_images(practice)
    html_string = render_to_string(
        "my_practice/intake_form_pdf.html",
        {"client": client, "practice": practice, "logo_data": logo_data, "lang": lang},
    )
    pdf_bytes = HTML(string=html_string).write_pdf(pdf_forms=True)
    safe_code = client.client_code.replace("/", "-")
    filename = f"Aufnahmebogen_{safe_code}.pdf" if lang == "de" else f"IntakeForm_{safe_code}.pdf"
    return pdf_bytes, filename


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


def _resolve_questionnaire_section(section: dict, lang: str, index: int) -> dict:
    """Resolve one raw content section to language + pre-computed field names.

    Field names are prefixed by section index (``s{index}_...``) so multiple
    sections in one document never collide, and computed here rather than via
    nested Django ``forloop.parentloop`` chains, keeping the template simple.

    Supported ``type`` values: ``grid`` (statement rows x response columns),
    ``checklist`` (statement rows with a single yes/no checkbox), ``freetext``
    (a prompt with N blank fillable lines).
    """
    intro = section.get("intro", {}).get(lang, "")

    if section["type"] == "grid":
        columns = [c[lang] for c in section["columns"]]
        rows = [
            {"label": item[lang], "field_name": f"s{index}_q{item_idx}"}
            for item_idx, item in enumerate(section["items"])
        ]
        return {"type": "grid", "intro": intro, "columns": columns, "rows": rows}

    if section["type"] == "checklist":
        rows = [
            {"label": item[lang], "field_name": f"s{index}_c{item_idx}"}
            for item_idx, item in enumerate(section["items"])
        ]
        return {"type": "checklist", "intro": intro, "rows": rows}

    if section["type"] == "freetext":
        n_lines = section.get("lines", 1)
        field_names = [f"s{index}_f{line_idx}" for line_idx in range(n_lines)]
        return {"type": "freetext", "intro": intro, "field_names": field_names}

    raise ValueError(f"Unknown questionnaire section type: {section['type']!r}")


def generate_questionnaire_pdf_bytes(code: str, practice: Practice, lang: str) -> tuple[bytes, str]:
    """Render a blank clinical questionnaire (e.g. GAD-7) as fillable PDF bytes.

    Unlike the intake form / contract PDFs, this is not tied to a specific
    client — the same bytes apply to anyone. Content (question text, response
    scale) comes from ``load_questionnaire``, not this template, so instruments
    with restrictive licensing never need their text committed to this repo.

    Returns:
        (pdf_bytes, filename) — filename is suitable for download or attachment.
    """
    content = load_questionnaire(code)
    logo_data, _signature = _prepare_practice_images(practice)
    sections = [
        _resolve_questionnaire_section(section, lang, index)
        for index, section in enumerate(content.sections)
    ]
    html_string = render_to_string(
        "my_practice/questionnaire_pdf.html",
        {
            "practice": practice,
            "logo_data": logo_data,
            "lang": lang,
            "title": content.title[lang],
            "intro": content.intro.get(lang, ""),
            "sections": sections,
        },
    )
    pdf_bytes = HTML(string=html_string).write_pdf(pdf_forms=True)
    filename = f"{content.code.upper()}_{lang}.pdf"
    return pdf_bytes, filename


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
        messages.error(request, str(e))
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
    logo_data, signature_data = _prepare_practice_images(practice)

    # Share FontConfiguration across all renders to avoid repeated font loading from disk.
    font_config = FontConfiguration()

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for invoice in invoices:
            pdf_bytes, filename = _render_invoice_pdf_bytes(
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

    invoice.status = new_status

    # Automatically set paid_date when status changes to paid
    if new_status == Invoice.Status.PAID and not invoice.paid_date:
        invoice.paid_date = date.today()
    # Clear paid_date if status is changed from paid to something else
    elif new_status != Invoice.Status.PAID and invoice.paid_date:
        invoice.paid_date = None

    invoice.save()

    # HTMX request: return just the badge HTML for #invoice-status-{pk}
    if request.headers.get("HX-Request"):
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

    next_url = request.POST.get("next")
    if next_url:
        return redirect(next_url)

    return JsonResponse(
        {
            "status": new_status,
            "display": invoice.get_status_display(),
            "paid_date": (invoice.paid_date.strftime("%d.%m.%Y") if invoice.paid_date else None),
        }
    )
