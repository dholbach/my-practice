"""
Add fillable AcroForm text fields to the contract PDF.

Uses pdfplumber (already a dependency) to locate sig-label positions
dynamically, then overlays text fields with pypdf — so no hardcoded
pixel coordinates and no recalibration needed if the template changes.
"""

import io
from typing import cast

import pdfplumber
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject as StringObject,
)

# Sig-line CSS: height 0.8cm, margin-bottom 0.1cm above the label.
# 1 cm = 28.346 PDF pts.
_SIG_LINE_HEIGHT_PT = 0.8 * 28.346  # ≈ 22.68
_SIG_LINE_GAP_PT = 0.1 * 28.346  # ≈ 2.83

# Page margins from @page rule (2 cm left/right, 1.5 cm bottom).
_LEFT_MARGIN_PT = 2.0 * 28.346  # ≈ 56.69
_RIGHT_EDGE_PT = 595.28 - _LEFT_MARGIN_PT  # ≈ 538.59  (A4 width - right margin)


def _classify_sig_label(first: str, next_text: str) -> tuple[str, str] | None:
    """
    Classify a sig-label snippet into (kind, tooltip), or None if *first*
    isn't one of the recognised DE/EN sig-label openers.
    """
    if first in ("(Ort,", "(Place,"):
        return "datum", "Ort, Datum / Place, date"
    if first == "(Unterschrift" and "Patient" in next_text:
        return "unterschrift_patient", "Unterschrift Patient/in"
    if first == "(Unterschrift" and "Heilpraktiker" in next_text:
        return "unterschrift_hp", "Unterschrift Therapeut/in"
    if first.startswith("(Patient"):
        return "unterschrift_patient", "Patient's signature"
    if first == "(Natural":
        return "unterschrift_hp", "Natural practitioner's signature"
    return None


def _build_field_spec(
    word: dict, kind: str, tooltip: str, page_num: int, page_height: float, mid_x: float
) -> dict:
    """Build a {page, name, tooltip, rect} spec for a sig-label word."""
    # pdfplumber: y=0 at top, increases downward.
    # pypdf:      y=0 at bottom, increases upward.
    label_top_plumber = float(word["top"])

    # The sig-line (0.8 cm) sits just above the label with a 0.1 cm gap.
    field_bottom_plumber = label_top_plumber - _SIG_LINE_GAP_PT
    field_top_plumber = field_bottom_plumber - _SIG_LINE_HEIGHT_PT

    y1 = page_height - field_bottom_plumber  # lower PDF y-coord
    y2 = page_height - field_top_plumber  # upper PDF y-coord

    label_x = float(word["x0"])
    is_left = label_x < mid_x
    x1 = _LEFT_MARGIN_PT if is_left else mid_x + 5
    x2 = (mid_x - 5) if is_left else _RIGHT_EDGE_PT

    side = "L" if is_left else "R"
    name = f"p{page_num + 1}_{kind}_{side}"

    return {"page": page_num, "name": name, "tooltip": tooltip, "rect": (x1, y1, x2, y2)}


def _detect_sig_fields(pdf_bytes: bytes) -> list[dict]:
    """
    Locate signature-label text in the PDF and return form-field specs.

    Sig-labels all start with '(' and are distinct short snippets:
      DE: (Ort, Datum)  (Unterschrift Patient/in)  (Unterschrift Heilpraktiker/in)
      EN: (Place, date) (Patient's signature)       (Natural practitioner's signature)

    Each spec: {page, name, tooltip, rect} where rect is
    (x1, y1, x2, y2) in PDF coords (origin bottom-left, y upward).
    """
    field_specs: list[dict] = []
    mid_x = (_LEFT_MARGIN_PT + _RIGHT_EDGE_PT) / 2  # ≈ 297.6

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            page_height = float(page.height)
            words = page.extract_words(x_tolerance=3, y_tolerance=3)

            for i, word in enumerate(words):
                first = word["text"]
                if not first.startswith("("):
                    continue

                # Peek at next word to classify the label type.
                next_text = words[i + 1]["text"] if i + 1 < len(words) else ""
                classified = _classify_sig_label(first, next_text)
                if classified is None:
                    continue
                kind, tooltip = classified

                field_specs.append(
                    _build_field_spec(word, kind, tooltip, page_num, page_height, mid_x)
                )

    return field_specs


def add_contract_form_fields(pdf_bytes: bytes) -> bytes:
    """
    Return a copy of *pdf_bytes* with fillable AcroForm text fields
    overlaid on every signature line in the contract PDF.

    The fields have no visible border (the sig-line already provides
    the visual underline), so existing clients see no change; PDF
    readers expose them as typeable text areas.
    """
    field_specs = _detect_sig_fields(pdf_bytes)
    if not field_specs:
        return pdf_bytes

    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    # Ensure an AcroForm dictionary exists.
    root = writer._root_object
    if NameObject("/AcroForm") not in root:
        acroform = DictionaryObject(
            {
                NameObject("/Fields"): ArrayObject(),
                NameObject("/DA"): StringObject("/Helv 9 Tf 0 g"),
                NameObject("/NeedAppearances"): BooleanObject(True),
            }
        )
        root[NameObject("/AcroForm")] = writer._add_object(acroform)

    acroform = cast(DictionaryObject, root[NameObject("/AcroForm")])

    for spec in field_specs:
        x1, y1, x2, y2 = spec["rect"]
        field = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Widget"),
                NameObject("/FT"): NameObject("/Tx"),
                NameObject("/T"): StringObject(spec["name"]),
                NameObject("/TU"): StringObject(spec["tooltip"]),
                NameObject("/DA"): StringObject("/Helv 9 Tf 0 g"),
                NameObject("/F"): NumberObject(4),  # printable
                NameObject("/Rect"): ArrayObject(
                    [FloatObject(x1), FloatObject(y1), FloatObject(x2), FloatObject(y2)]
                ),
                # No border — the sig-line in the template is the visual indicator.
                NameObject("/BS"): DictionaryObject(
                    {
                        NameObject("/W"): NumberObject(0),
                        NameObject("/S"): NameObject("/S"),
                    }
                ),
            }
        )
        field_ref = writer._add_object(field)

        # Attach to the page's /Annots array.
        page = writer.pages[spec["page"]]
        if NameObject("/Annots") not in page:
            page[NameObject("/Annots")] = ArrayObject()
        page[NameObject("/Annots")].append(field_ref)

        # Register in the AcroForm /Fields array.
        acroform[NameObject("/Fields")].append(field_ref)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
