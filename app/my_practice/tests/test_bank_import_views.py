"""
Tests for bank import views.

Covers: BankImportView, BankReviewView (bulk + single actions),
BankExpenseReviewView, BankWithdrawalReviewView.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import (
    BankTransaction,
    Client,
    CompanyExpense,
    CompanyWithdrawal,
    Invoice,
    InvoiceItem,
    Practice,
    ServiceType,
    Session,
    UserPractice,
)

PRACTICE_IBAN = "DE89370400440532013000"


def _make_invoice_item(invoice, practice, client_obj, rate=Decimal("90.00")):
    """Create the minimum supporting objects for an InvoiceItem."""
    service_type, _ = ServiceType.objects.get_or_create(
        code="test_therapy_60",
        defaults={"practice": practice, "name": "Therapy 60min"},
    )
    session = Session.objects.create(
        client=client_obj,
        session_date=date(2026, 1, 1),
        duration=60,
    )
    return InvoiceItem.objects.create(
        invoice=invoice,
        service_type=service_type,
        session=session,
        rate=rate,
        quantity=1,
    )


def _csv_bytes(rows, iban=PRACTICE_IBAN):
    header = (
        "IBAN Auftragskonto;Buchungstag;Valutadatum;"
        "Name Zahlungsbeteiligter;IBAN Zahlungsbeteiligter;"
        "Betrag;Saldo nach Buchung;Verwendungszweck"
    )
    lines = [header]
    lines.extend(
        ";".join(
            [
                iban,
                r.get("date", "15.01.2026"),
                r.get("date", "15.01.2026"),
                r.get("payer", "Test Zahler"),
                r.get("payer_iban", ""),
                r.get("amount", "90,00"),
                "1000,00",
                r.get("ref", "Test"),
            ]
        )
        for r in rows
    )
    return "\n".join(lines).encode("utf-8")


class BankImportViewBase(TestCase):
    """Shared setUp for bank import view tests."""

    def setUp(self):
        self.user = User.objects.create_user(username="bankuser", password="pass")
        self.practice = Practice.objects.create(
            name="Test Praxis",
            slug="bank-import-views",
            title="Therapeutin",
            email="test@example.com",
            iban=PRACTICE_IBAN,
        )
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)

        self.http = TestClient()
        self.http.login(username="bankuser", password="pass")
        session = self.http.session
        session["current_practice_slug"] = self.practice.slug
        session.save()


# ── BankImportView ────────────────────────────────────────────────────────────


class BankImportViewGetTest(BankImportViewBase):
    def test_get_loads(self):
        response = self.http.get(reverse("bank_import"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/bank_import.html")


class BankImportViewPostTest(BankImportViewBase):
    def _upload(self, rows, iban=PRACTICE_IBAN):
        csv_file = SimpleUploadedFile(
            "test.csv", _csv_bytes(rows, iban=iban), content_type="text/csv"
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


# ── BankReviewView ────────────────────────────────────────────────────────────


class BankReviewViewBase(BankImportViewBase):
    def _make_unmatched(self, ref="Test Ref", amount="90,00", payer="Jemand"):
        return BankTransaction.objects.create(
            practice=self.practice,
            transaction_date=date(2026, 1, 15),
            value_date=date(2026, 1, 15),
            payer_name=payer,
            payer_iban="",
            reference=ref,
            amount=Decimal(amount.replace(",", ".")),
            balance_after=Decimal("1000.00"),
            account_iban=PRACTICE_IBAN,
            match_confidence="unmatched",
            processed=False,
        )

    def _make_invoice(
        self, number="TS-1", status="sent", total=Decimal("90.00"), payer="Test Sender"
    ):
        client_obj = Client.objects.create(
            practice=self.practice,
            full_name=payer,
            client_code=number.split("-")[0],
        )
        invoice = Invoice.objects.create(
            practice=self.practice,
            client=client_obj,
            invoice_number=number,
            status=status,
            invoice_date=date(2026, 1, 1),
        )
        _make_invoice_item(invoice, self.practice, client_obj, rate=total)
        return invoice


class BankReviewViewGetTest(BankReviewViewBase):
    def test_get_loads(self):
        self._make_unmatched()
        response = self.http.get(reverse("bank_review"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/bank_review.html")

    def test_shows_only_unmatched(self):
        self._make_unmatched(ref="Unmatched One")
        # Also create a processed transaction (should not appear)
        BankTransaction.objects.create(
            practice=self.practice,
            transaction_date=date(2026, 1, 16),
            value_date=date(2026, 1, 16),
            payer_name="Done",
            payer_iban="",
            reference="Already done",
            amount=Decimal("50.00"),
            balance_after=Decimal("950.00"),
            account_iban=PRACTICE_IBAN,
            match_confidence="manual",
            processed=True,
        )
        response = self.http.get(reverse("bank_review"))
        transactions = response.context["transactions"]
        self.assertEqual(len(transactions), 1)


class BankReviewBulkActionsTest(BankReviewViewBase):
    def test_ignore_all_unmatched(self):
        self._make_unmatched(ref="Ref A")
        self._make_unmatched(ref="Ref B")
        response = self.http.post(reverse("bank_review"), {"action": "ignore_all_unmatched"})
        self.assertRedirects(response, reverse("bank_review"))
        self.assertEqual(BankTransaction.objects.filter(match_confidence="ignored").count(), 2)

    def test_ignore_all_expenses(self):
        self._make_unmatched(ref="Expense", amount="-120,00")
        self._make_unmatched(ref="Income", amount="90,00")  # positive, should NOT be ignored
        self.http.post(reverse("bank_review"), {"action": "ignore_all_expenses"})
        ignored = BankTransaction.objects.filter(match_confidence="ignored")
        self.assertEqual(ignored.count(), 1)
        self.assertEqual(ignored.first().reference, "Expense")

    def test_bulk_ignore_paid_matches_paid_invoice(self):
        self._make_invoice(number="BP-1", status="paid", total=Decimal("90.00"), payer="Bulk Payer")
        trans = self._make_unmatched(ref="BP-1", amount="90,00", payer="Bulk Payer")
        trans.extracted_invoice_number = "BP-1"
        trans.save()

        self.http.post(reverse("bank_review"), {"action": "bulk_ignore_paid"})
        trans.refresh_from_db()
        self.assertEqual(trans.match_confidence, "ignored")
        self.assertTrue(trans.processed)

    def test_bulk_ignore_paid_skips_amount_mismatch(self):
        self._make_invoice(number="BM-1", status="paid", total=Decimal("90.00"), payer="Bm Payer")
        trans = self._make_unmatched(ref="BM-1", amount="80,00", payer="Bm Payer")
        trans.extracted_invoice_number = "BM-1"
        trans.save()

        self.http.post(reverse("bank_review"), {"action": "bulk_ignore_paid"})
        trans.refresh_from_db()
        self.assertEqual(trans.match_confidence, "unmatched")  # unchanged


class BankReviewSingleActionsTest(BankReviewViewBase):
    def test_ignore_action(self):
        trans = self._make_unmatched(ref="To Ignore")
        self.http.post(
            reverse("bank_review"),
            {
                "action": "ignore",
                "transaction_id": trans.id,
            },
        )
        trans.refresh_from_db()
        self.assertEqual(trans.match_confidence, "ignored")
        self.assertTrue(trans.processed)

    def test_auto_match_marks_invoice_paid(self):
        invoice = self._make_invoice(
            number="AM-1", status="sent", total=Decimal("90.00"), payer="Auto Matcher"
        )
        trans = self._make_unmatched(ref="AM-1 Zahlung", amount="90,00")

        self.http.post(
            reverse("bank_review"),
            {
                "action": "auto_match",
                "transaction_id": trans.id,
                "suggested_invoice_id": invoice.id,
            },
        )

        trans.refresh_from_db()
        self.assertEqual(trans.match_confidence, "exact")
        self.assertEqual(trans.matched_invoice, invoice)

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")
        self.assertEqual(invoice.paid_date, date(2026, 1, 15))

    def test_auto_match_requires_sent_invoice(self):
        invoice = self._make_invoice(
            number="PA-1", status="paid", total=Decimal("90.00"), payer="Paid Already"
        )
        trans = self._make_unmatched(ref="PA-1")
        response = self.http.post(
            reverse("bank_review"),
            {
                "action": "auto_match",
                "transaction_id": trans.id,
                "suggested_invoice_id": invoice.id,
            },
        )
        # Should 404 because invoice is not "sent"
        self.assertEqual(response.status_code, 404)

    def test_confirm_paid_links_transaction(self):
        invoice = self._make_invoice(
            number="CP-1", status="paid", total=Decimal("90.00"), payer="Confirm Payer"
        )
        trans = self._make_unmatched(ref="CP-1")
        self.http.post(
            reverse("bank_review"),
            {
                "action": "confirm_paid",
                "transaction_id": trans.id,
                "suggested_invoice_id": invoice.id,
            },
        )
        trans.refresh_from_db()
        self.assertEqual(trans.match_confidence, "manual")
        self.assertTrue(trans.processed)
        self.assertEqual(trans.matched_invoice, invoice)

    def test_no_transaction_id_redirects(self):
        response = self.http.post(reverse("bank_review"), {"action": "ignore"})
        self.assertRedirects(response, reverse("bank_review"))


# ── BankExpenseReviewView ─────────────────────────────────────────────────────


class BankExpenseReviewViewTest(BankImportViewBase):
    def _make_expense_transaction(self, ref="Ausgabe Ref"):
        return BankTransaction.objects.create(
            practice=self.practice,
            transaction_date=date(2026, 1, 15),
            value_date=date(2026, 1, 15),
            payer_name="Vermieter",
            payer_iban="",
            reference=ref,
            amount=Decimal("-120.00"),
            balance_after=Decimal("880.00"),
            account_iban=PRACTICE_IBAN,
            match_confidence="unmatched",
            processed=False,
        )

    def test_get_loads(self):
        self._make_expense_transaction()
        response = self.http.get(reverse("bank_expense_review"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/bank_expense_review.html")

    def test_group_creates_expense(self):
        trans = self._make_expense_transaction()
        response = self.http.post(
            reverse("bank_expense_review"),
            {
                "action": "group",
                "transactions": [trans.id],
                "category": "miete",
                "description": "Praxismiete Januar",
            },
        )
        self.assertRedirects(response, reverse("bank_expense_review"))
        self.assertEqual(CompanyExpense.objects.filter(practice=self.practice).count(), 1)
        trans.refresh_from_db()
        self.assertTrue(trans.processed)

    def test_ignore_marks_transactions(self):
        trans = self._make_expense_transaction()
        self.http.post(
            reverse("bank_expense_review"),
            {
                "action": "ignore",
                "transactions": [trans.id],
            },
        )
        trans.refresh_from_db()
        self.assertEqual(trans.match_confidence, "ignored")
        self.assertTrue(trans.processed)


# ── BankWithdrawalReviewView ──────────────────────────────────────────────────


class BankWithdrawalReviewViewTest(BankImportViewBase):
    def _make_withdrawal_transaction(self, ref="Entnahme"):
        return BankTransaction.objects.create(
            practice=self.practice,
            transaction_date=date(2026, 1, 15),
            value_date=date(2026, 1, 15),
            payer_name="Praxisinhaber",
            payer_iban="",
            reference=ref,
            amount=Decimal("-500.00"),
            balance_after=Decimal("500.00"),
            account_iban=PRACTICE_IBAN,
            match_confidence="auto-withdrawal",
            processed=False,
        )

    def test_get_loads(self):
        self._make_withdrawal_transaction()
        response = self.http.get(reverse("bank_withdrawal_review"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/bank_withdrawal_review.html")

    def test_group_creates_withdrawal(self):
        trans = self._make_withdrawal_transaction()
        response = self.http.post(
            reverse("bank_withdrawal_review"),
            {
                "action": "group",
                "transactions": [trans.id],
                "category": "salary",
                "description": "Entnahme Januar",
            },
        )
        self.assertRedirects(response, reverse("bank_withdrawal_review"))
        self.assertEqual(
            CompanyWithdrawal.objects.filter(practice=self.practice, category="salary").count(), 1
        )
        trans.refresh_from_db()
        self.assertTrue(trans.processed)

    def test_ignore_deletes_linked_withdrawal(self):
        wd = CompanyWithdrawal.objects.create(
            practice=self.practice,
            date=date(2026, 1, 15),
            amount=Decimal("500.00"),
            description="Entnahme",
            category="salary",
        )
        trans = self._make_withdrawal_transaction()
        trans.linked_withdrawal = wd
        trans.save()

        self.http.post(
            reverse("bank_withdrawal_review"),
            {
                "action": "ignore",
                "transactions": [trans.id],
            },
        )
        self.assertFalse(CompanyWithdrawal.objects.filter(id=wd.id).exists())
        trans.refresh_from_db()
        self.assertEqual(trans.match_confidence, "ignored")
