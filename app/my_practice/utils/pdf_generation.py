"""
Render the practice's PDFs (invoice, contract, intake form, questionnaire) to bytes.

Shared by the download views (``views/api_views.py``) and the email views, which
attach the same bytes. HTTP concerns (responses, practice lookup, redirects) stay
in the views.
"""

import base64
import logging
import os
from io import BytesIO

from django.conf import settings
from django.core.cache import cache
from django.template.loader import render_to_string
from PIL import Image
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration

from ..models import Client, Invoice, Practice
from ..validators import PIL_IMAGE_FORMATS
from .case_sheet import working_diagnosis
from .contract_form import add_contract_form_fields
from .gebueh_helpers import build_gebueh_blocks, gebueh_total_for_blocks
from .questionnaire_content import load_questionnaire

logger = logging.getLogger(__name__)


def prepare_practice_images(
    practice: Practice,
) -> tuple[str | None, str | None]:
    """
    Load and optimise practice logo and signature images.

    Returns:
        (logo_data, signature_data) as base64-encoded JPEG strings, or None
        if the image is missing.

    Cached per practice — decoding/resizing is the same work on every PDF a
    practice generates (invoice, contract, intake form, questionnaire) until
    the logo or signature file actually changes. The cache key includes both
    file names, so a re-upload (which Django always saves under a new name)
    invalidates it automatically; nothing needs to clear the cache by hand.
    """
    logo_name = getattr(practice.logo, "name", None) or ""
    signature_name = getattr(practice.signature, "name", None) or ""
    cache_key = f"practice_pdf_images:{practice.pk}:{logo_name}:{signature_name}"

    cached: tuple[str | None, str | None] | None = cache.get(cache_key)
    if cached is not None:
        return cached

    logo_data: str | None = None
    signature_data: str | None = None

    for attr, max_size in (
        ("logo", (400, 160)),
        ("signature", (400, 160)),
    ):
        field = getattr(practice, attr, None)
        if not (field and os.path.exists(field.path)):
            continue
        try:
            img: Image.Image = Image.open(field.path, formats=PIL_IMAGE_FORMATS)
        except OSError:
            # Stored before uploads were held to PIL_IMAGE_FORMATS; the PDF
            # goes out without it rather than failing.
            logger.warning("Practice %s %s is not a supported image", practice.pk, attr)
            continue
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

    result = (logo_data, signature_data)
    cache.set(cache_key, result, None)
    return result


def render_invoice_pdf_bytes(
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
    if invoice.client.language == Client.Language.DE:
        lang = "de"
        filename = f"Rechnung_{invoice.invoice_number}.pdf"
    else:
        lang = "en"
        filename = f"Invoice_{invoice.invoice_number}.pdf"

    ctx: dict = {
        "invoice": invoice,
        "practice": practice,
        "lang": lang,
        "logo_data": logo_data,
        "signature_data": signature_data,
    }

    if invoice.client.needs_gebueh_invoice:
        ctx["gebueh_blocks"] = build_gebueh_blocks(invoice)
        ctx["gebueh_total"] = gebueh_total_for_blocks(ctx["gebueh_blocks"])
        ctx["arbeitsdiagnose"] = working_diagnosis(invoice.client)

    html_string = render_to_string("my_practice/invoice_pdf.html", ctx)
    # base_url lets WeasyPrint resolve static font files (fonts/ dir) relative to the app
    base_url = f"file://{settings.BASE_DIR}/static/"
    pdf_bytes = HTML(string=html_string, base_url=base_url).write_pdf(font_config=font_config)
    return pdf_bytes, filename


def generate_contract_pdf_bytes(client: Client, practice: Practice, lang: str) -> tuple[bytes, str]:
    """Render the pre-filled Behandlungsvertrag as PDF bytes.

    Returns:
        (pdf_bytes, filename) — filename is suitable for download or attachment.
    """
    logo_data, _signature = prepare_practice_images(practice)
    html_string = render_to_string(
        "my_practice/treatment_contract_pdf.html",
        {"client": client, "practice": practice, "logo_data": logo_data, "lang": lang},
    )
    pdf_bytes = HTML(string=html_string).write_pdf()
    pdf_bytes = add_contract_form_fields(pdf_bytes)
    safe_code = client.client_code.replace("/", "-")
    filename = (
        f"Behandlungsvertrag_{safe_code}.pdf"
        if lang == Client.Language.DE
        else f"TreatmentContract_{safe_code}.pdf"
    )
    return pdf_bytes, filename


def generate_intake_form_pdf_bytes(
    client: Client, practice: Practice, lang: str
) -> tuple[bytes, str]:
    """Render the pre-filled Aufnahmebogen as PDF bytes with fillable form fields.

    Returns:
        (pdf_bytes, filename) — filename is suitable for download or attachment.
    """
    logo_data, _signature = prepare_practice_images(practice)
    html_string = render_to_string(
        "my_practice/intake_form_pdf.html",
        {"client": client, "practice": practice, "logo_data": logo_data, "lang": lang},
    )
    pdf_bytes = HTML(string=html_string).write_pdf(pdf_forms=True)
    safe_code = client.client_code.replace("/", "-")
    filename = (
        f"Aufnahmebogen_{safe_code}.pdf"
        if lang == Client.Language.DE
        else f"IntakeForm_{safe_code}.pdf"
    )
    return pdf_bytes, filename


def resolve_questionnaire_section(section: dict, lang: str, index: int) -> dict:
    """Resolve one raw content section to language + pre-computed field names.

    Field names are prefixed by section index (``s{index}_...``) so multiple
    sections in one document never collide, and computed here rather than via
    nested Django ``forloop.parentloop`` chains, keeping the template simple.

    Supported ``type`` values: ``grid`` (statement rows x response columns;
    optionally multiple independent column groups per row, e.g. a
    "frequency" scale and a separate "duration" scale side by side),
    ``checklist`` (statement rows with a single yes/no checkbox), ``freetext``
    (a prompt with N blank fillable lines).
    """
    intro = section.get("intro", {}).get(lang, "")

    if section["type"] == "grid" and "column_groups" in section:
        column_groups = [
            {"label": g["label"][lang], "columns": [c[lang] for c in g["columns"]]}
            for g in section["column_groups"]
        ]
        rows = [
            {
                "label": item[lang],
                "groups": [
                    {
                        "field_name": f"s{index}_q{item_idx}_g{group_idx}",
                        "columns": group["columns"],
                    }
                    for group_idx, group in enumerate(column_groups)
                ],
            }
            for item_idx, item in enumerate(section["items"])
        ]
        return {"type": "grid", "intro": intro, "column_groups": column_groups, "rows": rows}

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
    logo_data, _signature = prepare_practice_images(practice)
    sections = [
        resolve_questionnaire_section(section, lang, index)
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
