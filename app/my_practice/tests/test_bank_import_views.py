"""
Tests for the bank import view: upload form and the match-form labels.
"""

from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from ..models import (
    Client,
    Invoice,
    Practice,
)
from .bank_import_helpers import PRACTICE_IBAN, BankImportViewBase, csv_bytes, make_invoice_item


class BankImportViewGetTest(BankImportViewBase):
    def test_get_loads(self):
        response = self.http.get(reverse("bank_import"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/bank_import.html")


class BankImportViewPostTest(BankImportViewBase):
    def _upload(self, rows, iban=PRACTICE_IBAN):
        csv_file = SimpleUploadedFile(
            "test.csv", csv_bytes(rows, iban=iban), content_type="text/csv"
        )
        return self.http.post(reverse("bank_import"), {"csv_file": csv_file})

    def test_valid_csv_redirects_to_review(self):
        response = self._upload(
            [
                {"date": "15.01.2026", "payer": "Jemand", "amount": "50,00", "ref": "Test"},
            ]
        )
        self.assertRedirects(response, reverse("bank_review"))

    def test_account_mismatch_shows_error(self):
        response = self._upload(
            [{"date": "15.01.2026", "payer": "Jemand", "amount": "50,00", "ref": "Test"}],
            iban="DE00000000000000000000",
        )
        # Should re-render the form (not redirect) when IBAN doesn't match
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/bank_import.html")


class TransactionMatchFormLabelTest(TestCase):
    """The manual-match dropdown labels invoices with German-formatted amounts."""

    def test_invoice_label_uses_german_currency_format(self):
        from ..import_forms import TransactionMatchForm

        practice = Practice.objects.create(name="Label Practice", slug="label-practice", title="T")
        client_obj = Client.objects.create(
            client_code="LB", full_name="Max Mustermann", practice=practice
        )
        invoice = Invoice.objects.create(
            client=client_obj,
            invoice_number="LB-1",
            invoice_date=date(2026, 1, 15),
            status="sent",
            practice=practice,
        )
        make_invoice_item(invoice, practice, client_obj, rate=Decimal("1090.00"))

        form = TransactionMatchForm(practice=practice)
        label = form.fields["invoice"].label_from_instance(invoice)

        # Used to be "LB-1 (2026-01-15): 1 090.00 €".
        self.assertEqual(label, "LB-1 (2026-01-15): 1.090,00 €")
