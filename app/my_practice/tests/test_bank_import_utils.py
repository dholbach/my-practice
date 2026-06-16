"""
Tests for BankStatementImporter utility class.

Covers: CSV parsing, invoice number extraction, invoice matching,
withdrawal/expense auto-detection, duplicate prevention, and end-to-end CSV processing.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from ..models import (
    BankTransaction,
    Client,
    ClientAlias,
    CompanyExpense,
    CompanyWithdrawal,
    Invoice,
    InvoiceItem,
    Practice,
    ServiceType,
    Session,
)
from ..utils import BankStatementImporter

PRACTICE_IBAN = "DE89370400440532013000"
PRIVATE_IBAN = "DE73200400600056789000"


def _make_importer(practice, rows, csv_iban=PRACTICE_IBAN):
    """Build a BankStatementImporter with a fake CSV file."""
    header = (
        "IBAN Auftragskonto;Buchungstag;Valutadatum;"
        "Name Zahlungsbeteiligter;IBAN Zahlungsbeteiligter;"
        "Betrag;Saldo nach Buchung;Verwendungszweck"
    )
    lines = [header]
    lines.extend(
        ";".join(
            [
                csv_iban,
                r.get("date", "15.01.2026"),
                r.get("date", "15.01.2026"),
                r.get("payer", "Test Zahler"),
                r.get("payer_iban", ""),
                r.get("amount", "90,00"),
                "1000,00",
                r.get("ref", "Überweisung"),
            ]
        )
        for r in rows
    )
    content = "\n".join(lines).encode("utf-8")
    csv_file = SimpleUploadedFile("test.csv", content, content_type="text/csv")
    return BankStatementImporter(csv_file, practice)


def _make_practice(**kwargs):
    defaults = dict(
        name="Test Praxis",
        slug="bank-util-test",
        title="Therapeutin",
        email="test@example.com",
        iban=PRACTICE_IBAN,
    )
    defaults.update(kwargs)
    return Practice.objects.create(**defaults)


def _make_invoice_item(invoice, practice, client_obj, rate=Decimal("90.00"), duration=60):
    """Create the minimum required objects for an InvoiceItem."""
    service_type, _ = ServiceType.objects.get_or_create(
        code=f"test_therapy_{duration}",
        defaults={"practice": practice, "name": f"Therapy {duration}min"},
    )
    session = Session.objects.create(
        client=client_obj,
        session_date=date(2026, 1, 1),
        duration=duration,
    )
    return InvoiceItem.objects.create(
        invoice=invoice,
        service_type=service_type,
        session=session,
        rate=rate,
        quantity=1,
    )


# ── parse_german_decimal ──────────────────────────────────────────────────────


class ParseGermanDecimalTest(TestCase):
    def setUp(self):
        self.practice = _make_practice(slug="parse-decimal")
        self.importer = _make_importer(self.practice, [])

    def test_positive(self):
        self.assertEqual(self.importer.parse_german_decimal("90,00"), Decimal("90.00"))

    def test_negative(self):
        self.assertEqual(self.importer.parse_german_decimal("-300,00"), Decimal("-300.00"))

    def test_zero(self):
        self.assertEqual(self.importer.parse_german_decimal("0,00"), Decimal("0.00"))

    def test_invalid_raises(self):
        with self.assertRaises(InvalidOperation):
            self.importer.parse_german_decimal("nicht-eine-zahl")


# ── parse_german_date ─────────────────────────────────────────────────────────


class ParseGermanDateTest(TestCase):
    def setUp(self):
        self.practice = _make_practice(slug="parse-date")
        self.importer = _make_importer(self.practice, [])

    def test_valid_date(self):
        self.assertEqual(self.importer.parse_german_date("02.02.2026"), date(2026, 2, 2))

    def test_leading_zeros(self):
        self.assertEqual(self.importer.parse_german_date("01.01.2026"), date(2026, 1, 1))

    def test_iso_format_raises(self):
        with self.assertRaises(ValueError):
            self.importer.parse_german_date("2026-02-02")


# ── extract_invoice_number ────────────────────────────────────────────────────


class ExtractInvoiceNumberTest(TestCase):
    def setUp(self):
        self.practice = _make_practice(slug="extract-inv")
        self.importer = _make_importer(self.practice, [])

    def test_direct_code(self):
        self.assertEqual(self.importer.extract_invoice_number("LI-3"), "LI-3")

    def test_direct_code_longer(self):
        self.assertEqual(self.importer.extract_invoice_number("ABCD-123"), "ABCD-123")

    def test_rechnung_keyword(self):
        self.assertEqual(self.importer.extract_invoice_number("Rechnung Nr. OW-1"), "OW-1")

    def test_invoice_keyword(self):
        self.assertEqual(self.importer.extract_invoice_number("Invoice No. EC-9"), "EC-9")

    def test_therapie_context(self):
        self.assertEqual(self.importer.extract_invoice_number("3x Therapie JL-3"), "JL-3")

    def test_uppercase_normalised(self):
        self.assertEqual(self.importer.extract_invoice_number("ab-12"), "AB-12")

    def test_no_match_time(self):
        self.assertIsNone(self.importer.extract_invoice_number("Mi 9-10"))

    def test_no_match_plain_text(self):
        self.assertIsNone(self.importer.extract_invoice_number("Überweisung Miete"))

    def test_no_match_single_letter(self):
        # Single letter codes must not be extracted (min 2 letters)
        self.assertIsNone(self.importer.extract_invoice_number("A-1"))


# ── find_matching_invoice ─────────────────────────────────────────────────────


class FindMatchingInvoiceTest(TestCase):
    def setUp(self):
        self.practice = _make_practice(slug="find-invoice")
        self.client_obj = Client.objects.create(
            practice=self.practice,
            full_name="Anna Schmidt",
            client_code="AS",
        )
        self.invoice = Invoice.objects.create(
            practice=self.practice,
            client=self.client_obj,
            invoice_number="AS-1",
            status="sent",
            invoice_date=date(2026, 1, 1),
        )
        _make_invoice_item(self.invoice, self.practice, self.client_obj)
        self.importer = _make_importer(self.practice, [])

    def test_exact_name_match(self):
        result = self.importer.find_matching_invoice("AS-1", Decimal("90.00"), "Anna Schmidt")
        self.assertIsNotNone(result)
        invoice, confidence = result
        self.assertEqual(invoice, self.invoice)
        self.assertEqual(confidence, "exact")

    def test_different_name_still_exact(self):
        # Name mismatch but no alias → still returns exact (user can add alias later)
        result = self.importer.find_matching_invoice("AS-1", Decimal("90.00"), "Unbekannt")
        self.assertIsNotNone(result)
        _, confidence = result
        self.assertEqual(confidence, "exact")

    def test_fuzzy_match_via_alias(self):
        ClientAlias.objects.create(client=self.client_obj, alias_name="A. Schmidt")
        result = self.importer.find_matching_invoice("AS-1", Decimal("90.00"), "A. Schmidt")
        self.assertIsNotNone(result)
        _, confidence = result
        self.assertEqual(confidence, "fuzzy")

    def test_amount_mismatch_returns_none(self):
        result = self.importer.find_matching_invoice("AS-1", Decimal("80.00"), "Anna Schmidt")
        self.assertIsNone(result)

    def test_wrong_invoice_number(self):
        result = self.importer.find_matching_invoice("XX-99", Decimal("90.00"), "Anna Schmidt")
        self.assertIsNone(result)

    def test_paid_invoice_not_matched(self):
        self.invoice.status = "paid"
        self.invoice.save()
        result = self.importer.find_matching_invoice("AS-1", Decimal("90.00"), "Anna Schmidt")
        self.assertIsNone(result)


# ── detect_and_create_financial_record ───────────────────────────────────────


class DetectFinancialRecordTest(TestCase):
    def setUp(self):
        self.practice = _make_practice(
            slug="detect-financial",
            private_bank_account=PRIVATE_IBAN,
        )
        self.importer = _make_importer(self.practice, [])
        self.txn_date = date(2026, 2, 1)

    def test_iban_match_creates_withdrawal(self):
        result = self.importer.detect_and_create_financial_record(
            self.txn_date, Decimal("-300.00"), "Entnahme", payer_iban=PRIVATE_IBAN
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "CompanyWithdrawal")
        self.assertEqual(CompanyWithdrawal.objects.filter(practice=self.practice).count(), 1)

    def test_withdrawal_category_private_transfer(self):
        result = self.importer.detect_and_create_financial_record(
            self.txn_date, Decimal("-300.00"), "Überweisung", payer_iban=PRIVATE_IBAN
        )
        self.assertEqual(result["record"].category, "private_transfer")

    def test_correction_keyword_sets_category(self):
        result = self.importer.detect_and_create_financial_record(
            self.txn_date, Decimal("-50.00"), "Fehlbuchung Korrektur", payer_iban=PRIVATE_IBAN
        )
        self.assertEqual(result["record"].category, "correction")

    def test_salary_keyword_sets_category(self):
        result = self.importer.detect_and_create_financial_record(
            self.txn_date, Decimal("-2000.00"), "Entnahme Unternehmerlohn", payer_iban=PRIVATE_IBAN
        )
        self.assertEqual(result["record"].category, "salary")

    def test_keyword_fallback_without_iban(self):
        # No private IBAN configured → keyword-only fallback
        practice_no_iban = _make_practice(slug="no-private-iban")
        importer = _make_importer(practice_no_iban, [])
        result = importer.detect_and_create_financial_record(
            self.txn_date, Decimal("-2000.00"), "Unternehmerlohn Jan 2026"
        )
        self.assertEqual(result["type"], "CompanyWithdrawal")

    def test_unrelated_expense_creates_expense(self):
        practice_no_iban = _make_practice(slug="expense-test")
        importer = _make_importer(practice_no_iban, [])
        result = importer.detect_and_create_financial_record(
            self.txn_date, Decimal("-120.00"), "Miete Praxisraum"
        )
        self.assertEqual(result["type"], "CompanyExpense")
        self.assertEqual(CompanyExpense.objects.filter(practice=practice_no_iban).count(), 1)

    def test_idempotent_duplicate(self):
        r1 = self.importer.detect_and_create_financial_record(
            self.txn_date, Decimal("-300.00"), "Entnahme", payer_iban=PRIVATE_IBAN
        )
        r2 = self.importer.detect_and_create_financial_record(
            self.txn_date, Decimal("-300.00"), "Entnahme", payer_iban=PRIVATE_IBAN
        )
        self.assertEqual(r1["record"].id, r2["record"].id)
        self.assertEqual(CompanyWithdrawal.objects.filter(practice=self.practice).count(), 1)


# ── process (end-to-end CSV) ──────────────────────────────────────────────────


class ProcessCSVTest(TestCase):
    def setUp(self):
        self.practice = _make_practice(slug="process-csv")
        self.client_obj = Client.objects.create(
            practice=self.practice, full_name="Max Mustermann", client_code="MM"
        )
        self.invoice = Invoice.objects.create(
            practice=self.practice,
            client=self.client_obj,
            invoice_number="MM-1",
            status="sent",
            invoice_date=date(2026, 1, 1),
        )
        _make_invoice_item(self.invoice, self.practice, self.client_obj)

    def test_matched_invoice_marks_paid(self):
        importer = _make_importer(
            self.practice,
            [
                {"date": "15.01.2026", "payer": "Max Mustermann", "amount": "90,00", "ref": "MM-1"},
            ],
        )
        results = importer.process(skip_negatives=False)
        self.assertEqual(results["matched"], 1)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "paid")

    def test_unmatched_transaction(self):
        importer = _make_importer(
            self.practice,
            [
                {
                    "date": "15.01.2026",
                    "payer": "Unbekannt",
                    "amount": "50,00",
                    "ref": "Überweisung",
                },
            ],
        )
        results = importer.process(skip_negatives=False)
        self.assertEqual(results["unmatched"], 1)
        self.assertEqual(BankTransaction.objects.count(), 1)

    def test_duplicate_row_ignored(self):
        importer = _make_importer(
            self.practice,
            [
                {"date": "15.01.2026", "payer": "Jemand", "amount": "50,00", "ref": "Test Ref"},
                {"date": "15.01.2026", "payer": "Jemand", "amount": "50,00", "ref": "Test Ref"},
            ],
        )
        results = importer.process(skip_negatives=False)
        self.assertEqual(results["total"], 2)
        self.assertEqual(BankTransaction.objects.count(), 1)

    def test_account_mismatch_aborts(self):
        importer = _make_importer(
            self.practice,
            [{"date": "15.01.2026", "payer": "Jemand", "amount": "100,00", "ref": "Test"}],
            csv_iban="DE00000000000000000000",
        )
        results = importer.process()
        self.assertTrue(results.get("account_mismatch"))
        self.assertEqual(BankTransaction.objects.count(), 0)

    def test_negative_skipped_when_not_withdrawal(self):
        # No private IBAN → no withdrawal detection → auto-expense is created regardless
        # but skip_negatives=True should still ignore unknown negatives after auto-create fails
        importer = _make_importer(
            self.practice,
            [
                {"date": "15.01.2026", "payer": "Vermieter", "amount": "-500,00", "ref": "Miete"},
            ],
        )
        results = importer.process(skip_negatives=True)
        # With no private IBAN, "Miete" has no keyword match → CompanyExpense created,
        # transaction recorded with auto-expense confidence
        self.assertEqual(results["needs_review"], 1)

    def test_negative_not_skipped_when_skip_negatives_false(self):
        importer = _make_importer(
            self.practice,
            [
                {"date": "15.01.2026", "payer": "Vermieter", "amount": "-500,00", "ref": "Miete"},
            ],
        )
        results = importer.process(skip_negatives=False)
        self.assertEqual(results["needs_review"], 1)
