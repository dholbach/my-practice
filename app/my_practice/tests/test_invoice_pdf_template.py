"""The merged invoice PDF template renders the right language and fields (HTML only, no WeasyPrint)."""

from decimal import Decimal

from django.template.loader import render_to_string
from django.test import TestCase

from ..models import Client, Invoice, InvoiceItem, ServiceType, Session
from .test_helpers import create_test_practice


class InvoicePdfTemplateTests(TestCase):
    def setUp(self):
        self.practice = create_test_practice(
            slug="invoice-pdf-template-1",
            subtitle_de="Untertitel DE",
            subtitle_en="Subtitle EN",
            memberships_de="Mitgliedschaft DE",
            memberships_en="Membership EN",
            kleinunternehmer_text_de="Kleinunternehmer DE",
            kleinunternehmer_text_en="Small business EN",
            vat_exempt_text_de="Umsatzsteuerfrei DE",
            vat_exempt_text_en="VAT exempt EN",
            payment_terms_text_de="Zahlungsziel DE",
            payment_terms_text_en="Payment terms EN",
        )
        service = ServiceType.objects.create(
            code="pdf_60",
            name="Generic 60",
            name_de="Einzelsitzung",
            name_en="Single session",
            practice=self.practice,
        )
        self.client_obj = Client.objects.create(
            practice=self.practice,
            client_code="PT",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
        )
        self.invoice = Invoice.objects.create(
            practice=self.practice, client=self.client_obj, invoice_number="INV-001"
        )
        session = Session.objects.create(
            client=self.client_obj, session_date=self.invoice.invoice_date, duration=60
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=service,
            session=session,
            rate=Decimal("90.00"),
            quantity=1,
        )

    def _render(self, lang):
        return render_to_string(
            "my_practice/invoice_pdf.html",
            {"invoice": self.invoice, "practice": self.practice, "lang": lang},
        )

    def test_german_uses_german_labels_and_fields(self):
        html = self._render("de")
        self.assertIn('<html lang="de">', html)
        for text in (
            "<h1>Rechnung</h1>",
            "Rechnung an",
            "Bankverbindung",
            "Gesamtbetrag",
            "Einzelsitzung",
            "Untertitel DE",
            "Mitgliedschaft DE",
            "Umsatzsteuerfrei DE",
            "Zahlungsziel DE",
            "Alle Leistungen wurden für Max Mustermann erbracht.",
        ):
            self.assertIn(text, html)
        self.assertNotIn(" EN<", html)

    def test_english_uses_english_labels_and_fields(self):
        html = self._render("en")
        self.assertIn('<html lang="en">', html)
        for text in (
            "<h1>Invoice</h1>",
            "Bill to",
            "Bank Details",
            "Total",
            "Single session",
            "Subtitle EN",
            "Membership EN",
            "VAT exempt EN",
            "Payment terms EN",
            "All services were provided to Max Mustermann.",
        ):
            self.assertIn(text, html)
        for german in ("Rechnung", "Bankverbindung", "Gesamtbetrag", " DE<"):
            self.assertNotIn(german, html)

    def test_kleinunternehmer_text_replaces_the_vat_exempt_note(self):
        self.practice.is_kleinunternehmer = True
        self.assertIn("Small business EN", self._render("en"))
        self.assertNotIn("VAT exempt EN", self._render("en"))
        self.assertIn("Kleinunternehmer DE", self._render("de"))
