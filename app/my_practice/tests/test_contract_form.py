"""
Tests for contract_form.py — sig-label detection and AcroForm field overlay.
"""

import io
from decimal import Decimal

from django.template.loader import render_to_string
from django.test import TestCase
from pypdf import PdfReader
from weasyprint import HTML

from ..models import Client, Practice
from ..utils.contract_form import (
    _build_field_spec,
    _classify_sig_label,
    _detect_sig_fields,
    add_contract_form_fields,
)


def _render_raw_contract_pdf(client: Client, practice: Practice, lang: str) -> bytes:
    """Render the contract PDF *without* the AcroForm field overlay."""
    html_string = render_to_string(
        "my_practice/treatment_contract_pdf.html",
        {"client": client, "practice": practice, "logo_data": None, "lang": lang},
    )
    return HTML(string=html_string).write_pdf()


class ClassifySigLabelTest(TestCase):
    """Unit tests for the sig-label classifier."""

    def test_german_datum_label(self):
        self.assertEqual(
            _classify_sig_label("(Ort,", "Datum)"), ("datum", "Ort, Datum / Place, date")
        )

    def test_english_datum_label(self):
        self.assertEqual(
            _classify_sig_label("(Place,", "date)"), ("datum", "Ort, Datum / Place, date")
        )

    def test_german_patient_signature(self):
        self.assertEqual(
            _classify_sig_label("(Unterschrift", "Patient/in)"),
            ("unterschrift_patient", "Unterschrift Patient/in"),
        )

    def test_german_practitioner_signature(self):
        self.assertEqual(
            _classify_sig_label("(Unterschrift", "Heilpraktiker/in)"),
            ("unterschrift_hp", "Unterschrift Therapeut/in"),
        )

    def test_english_patient_signature(self):
        self.assertEqual(
            _classify_sig_label("(Patient's", "signature)"),
            ("unterschrift_patient", "Patient's signature"),
        )

    def test_english_practitioner_signature(self):
        self.assertEqual(
            _classify_sig_label("(Natural", "practitioner's"),
            ("unterschrift_hp", "Natural practitioner's signature"),
        )

    def test_unrecognised_label_returns_none(self):
        self.assertIsNone(_classify_sig_label("(Something", "else)"))


class BuildFieldSpecTest(TestCase):
    """Unit tests for the field-rect geometry builder."""

    def test_left_side_field(self):
        word = {"top": 700.0, "x0": 60.0}
        spec = _build_field_spec(
            word, "datum", "tooltip", page_num=0, page_height=841.89, mid_x=297.6
        )
        self.assertEqual(spec["page"], 0)
        self.assertEqual(spec["name"], "p1_datum_L")
        self.assertEqual(spec["tooltip"], "tooltip")
        x1, y1, x2, y2 = spec["rect"]
        self.assertLess(x1, 297.6)
        self.assertLess(y1, y2)

    def test_right_side_field(self):
        word = {"top": 700.0, "x0": 400.0}
        spec = _build_field_spec(
            word, "unterschrift_patient", "tooltip", page_num=1, page_height=841.89, mid_x=297.6
        )
        self.assertEqual(spec["name"], "p2_unterschrift_patient_R")
        x1, _y1, x2, _y2 = spec["rect"]
        self.assertGreaterEqual(x1, 297.6)


class DetectAndOverlaySigFieldsTest(TestCase):
    """Integration tests against a real rendered contract PDF."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="contract-form-test",
            title="Heilpraktikerin für Psychotherapie",
            email="practice@example.com",
            city="Berlin",
        )
        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

    def test_detects_three_sig_fields_in_german_contract(self):
        pdf_bytes = _render_raw_contract_pdf(self.test_client, self.practice, "de")
        specs = _detect_sig_fields(pdf_bytes)
        self.assertGreaterEqual(len(specs), 3)
        tooltips = {s["tooltip"] for s in specs}
        self.assertIn("Ort, Datum / Place, date", tooltips)
        self.assertIn("Unterschrift Patient/in", tooltips)
        self.assertIn("Unterschrift Therapeut/in", tooltips)

    def test_detects_three_sig_fields_in_english_contract(self):
        pdf_bytes = _render_raw_contract_pdf(self.test_client, self.practice, "en")
        specs = _detect_sig_fields(pdf_bytes)
        tooltips = {s["tooltip"] for s in specs}
        self.assertIn("Ort, Datum / Place, date", tooltips)
        self.assertIn("Patient's signature", tooltips)
        self.assertIn("Natural practitioner's signature", tooltips)

    def test_add_contract_form_fields_overlays_acroform_fields(self):
        pdf_bytes = _render_raw_contract_pdf(self.test_client, self.practice, "de")
        specs = _detect_sig_fields(pdf_bytes)

        overlaid = add_contract_form_fields(pdf_bytes)
        reader = PdfReader(io.BytesIO(overlaid))
        fields = reader.get_fields() or {}

        self.assertEqual(len(fields), len(specs))
        for spec in specs:
            self.assertIn(spec["name"], fields)

    def test_add_contract_form_fields_is_noop_without_sig_labels(self):
        # A PDF with no recognisable sig-label text should pass through unchanged.
        html_string = "<html><body><p>No signature labels here.</p></body></html>"
        pdf_bytes = HTML(string=html_string).write_pdf()
        result = add_contract_form_fields(pdf_bytes)
        self.assertEqual(result, pdf_bytes)
