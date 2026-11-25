"""Tests for bank_review_helpers: invoice matching and payer names on the review page."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from ..models import (
    BankTransaction,
    Client,
    ClientAlias,
    Invoice,
    InvoiceItem,
    ServiceType,
    Session,
    allow_issued_invoice_writes,
)
from ..utils.bank_import import amounts_match
from ..utils.bank_matching import ignore_already_paid, ignore_unmatched
from ..utils.bank_review_helpers import (
    annotate_review_rows,
    fetch_invoice_maps,
    known_payer_names,
    paid_invoice_matches,
    review_page_stats,
)
from .test_helpers import create_test_practice


class AmountsMatchTests(TestCase):
    def test_equal_and_sub_cent_differences_match(self):
        self.assertTrue(amounts_match(Decimal("90.00"), Decimal("90.00")))
        self.assertTrue(amounts_match(Decimal("90.00"), Decimal("90.009")))

    def test_a_cent_or_more_does_not_match(self):
        self.assertFalse(amounts_match(Decimal("90.00"), Decimal("90.01")))
        self.assertFalse(amounts_match(Decimal("90.00"), Decimal("89.99")))


class BankReviewHelperBase(TestCase):
    def setUp(self):
        self.practice = create_test_practice(slug="bank-review-helpers-1")
        self.other = create_test_practice(name="Other Practice", slug="bank-review-helpers-2")

    @allow_issued_invoice_writes()
    def make_invoice(
        self, number, status="sent", rate="90.00", practice=None, payer="Max Mustermann"
    ):
        practice = practice or self.practice
        client = Client.objects.create(
            practice=practice, full_name=payer, client_code=number.split("-")[0]
        )
        invoice = Invoice.objects.create(
            practice=practice,
            client=client,
            invoice_number=number,
            status=status,
            invoice_date=date(2026, 1, 1),
        )
        service_type, _ = ServiceType.objects.get_or_create(
            code="test_therapy_60", defaults={"practice": practice, "name": "Therapy 60min"}
        )
        session = Session.objects.create(client=client, session_date=date(2026, 1, 1), duration=60)
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=service_type,
            session=session,
            rate=Decimal(rate),
            quantity=1,
        )
        invoice.refresh_from_db()
        return invoice

    def make_transaction(self, number="", amount="90.00", payer="Jemand"):
        # The unique key includes the reference, so every row needs its own.
        self._transactions = getattr(self, "_transactions", 0) + 1
        return BankTransaction.objects.create(
            practice=self.practice,
            transaction_date=date(2026, 1, 15),
            value_date=date(2026, 1, 15),
            payer_name=payer,
            payer_iban="",
            reference=f"{number} #{self._transactions}",
            extracted_invoice_number=number,
            amount=Decimal(amount),
            balance_after=Decimal("1000.00"),
            account_iban="DE89370400440532013000",
            match_confidence="unmatched",
            processed=False,
        )


class FetchInvoiceMapsTests(BankReviewHelperBase):
    def test_splits_by_status_and_ignores_other_statuses(self):
        self.make_invoice("AA-1", status="paid")
        self.make_invoice("BB-1", status="sent")
        self.make_invoice("CC-1", status="draft")
        maps = fetch_invoice_maps(
            {"AA-1", "BB-1", "CC-1"}, ["paid", "sent"], practice=self.practice
        )
        self.assertEqual(set(maps["paid"]), {"AA-1"})
        self.assertEqual(set(maps["sent"]), {"BB-1"})

    def test_no_numbers_means_empty_maps(self):
        self.assertEqual(
            fetch_invoice_maps(set(), ["paid", "sent"], practice=self.practice),
            {"paid": {}, "sent": {}},
        )

    def test_other_practices_and_no_practice_see_nothing(self):
        self.make_invoice("AA-1", status="paid")
        self.assertEqual(fetch_invoice_maps({"AA-1"}, ["paid"], practice=self.other)["paid"], {})
        self.assertEqual(fetch_invoice_maps({"AA-1"}, ["paid"], practice=None)["paid"], {})


class KnownPayerNamesTests(BankReviewHelperBase):
    def test_client_names_and_aliases_are_lowercased_and_trimmed(self):
        invoice = self.make_invoice("AA-1", payer="  Anna Schmidt ")
        ClientAlias.objects.create(client=invoice.client, alias_name="A. Schmidt")
        self.assertEqual(known_payer_names(practice=self.practice), {"anna schmidt", "a. schmidt"})

    def test_other_practices_names_are_not_known(self):
        self.make_invoice("AA-1", practice=self.other, payer="Maria Musterfrau")
        self.assertEqual(known_payer_names(practice=self.practice), set())


class AnnotateReviewRowsTests(BankReviewHelperBase):
    def test_marks_matching_paid_and_unpaid_invoices(self):
        paid = self.make_invoice("AA-1", status="paid")
        sent = self.make_invoice("BB-1", status="sent")
        t_paid = self.make_transaction("AA-1")
        t_sent = self.make_transaction("BB-1")
        annotate_review_rows([t_paid, t_sent], practice=self.practice)
        self.assertEqual(t_paid.matching_paid_invoice, paid)
        self.assertIsNone(t_paid.matching_unpaid_invoice)
        self.assertEqual(t_sent.matching_unpaid_invoice, sent)
        self.assertIsNone(t_sent.matching_paid_invoice)

    def test_an_amount_mismatch_or_missing_number_matches_nothing(self):
        self.make_invoice("AA-1", status="paid")
        wrong_amount = self.make_transaction("AA-1", amount="80.00")
        no_number = self.make_transaction("")
        annotate_review_rows([wrong_amount, no_number], practice=self.practice)
        for transaction in (wrong_amount, no_number):
            self.assertIsNone(transaction.matching_paid_invoice)
            self.assertIsNone(transaction.matching_unpaid_invoice)

    def test_payer_name_known_by_client_name_or_alias(self):
        invoice = self.make_invoice("AA-1", payer="Max Mustermann")
        ClientAlias.objects.create(client=invoice.client, alias_name="M. Mustermann")
        by_name = self.make_transaction(payer="MAX MUSTERMANN ")
        by_alias = self.make_transaction(payer="M. Mustermann")
        stranger = self.make_transaction(payer="Jemand")
        no_name = self.make_transaction(payer="")
        annotate_review_rows([by_name, by_alias, stranger, no_name], practice=self.practice)
        self.assertEqual(
            [t.payer_name_known for t in (by_name, by_alias, stranger, no_name)],
            [True, True, False, False],
        )


class PaidInvoiceMatchesTests(BankReviewHelperBase):
    def test_pairs_only_transactions_matching_a_paid_invoice(self):
        paid = self.make_invoice("AA-1", status="paid")
        self.make_invoice("BB-1", status="sent")
        match = self.make_transaction("AA-1")
        sent_only = self.make_transaction("BB-1")
        mismatch = self.make_transaction("AA-1", amount="12.00")
        pairs = paid_invoice_matches([match, sent_only, mismatch], practice=self.practice)
        self.assertEqual(pairs, [(match, paid)])


Confidence = BankTransaction.Confidence


class ReviewPageStatsTests(BankReviewHelperBase):
    def test_counts_only_unprocessed_rows_of_the_practice(self):
        unmatched = self.make_transaction("AA-1", amount="-20.00")
        BankTransaction.objects.filter(pk=unmatched.pk).update(
            match_confidence=Confidence.AUTO_EXPENSE
        )
        withdrawal = self.make_transaction("BB-1", amount="-5.00")
        BankTransaction.objects.filter(pk=withdrawal.pk).update(
            match_confidence=Confidence.AUTO_WITHDRAWAL
        )
        done = self.make_transaction("CC-1")
        BankTransaction.objects.filter(pk=done.pk).update(processed=True)
        elsewhere = self.make_transaction("DD-1", amount="-1.00")
        BankTransaction.objects.filter(pk=elsewhere.pk).update(practice=self.other)

        stats = review_page_stats(practice=self.practice)

        self.assertEqual(
            stats["stats"], {Confidence.AUTO_EXPENSE: 1, Confidence.AUTO_WITHDRAWAL: 1}
        )
        self.assertEqual(stats["expense_count"], 1)

    def test_recently_matched_lists_matched_invoices_only(self):
        matched = self.make_transaction("AA-1")
        BankTransaction.objects.filter(pk=matched.pk).update(
            match_confidence=Confidence.EXACT, matched_invoice=self.make_invoice("AA-1")
        )
        self.make_transaction("BB-1")

        self.assertEqual(
            [t.pk for t in review_page_stats(practice=self.practice)["recently_matched"]],
            [matched.pk],
        )

    def test_no_practice_gives_empty_stats(self):
        self.make_transaction("AA-1")
        stats = review_page_stats(practice=None)
        self.assertEqual(stats["stats"], {})
        self.assertEqual(stats["expense_count"], 0)


class IgnoreTests(BankReviewHelperBase):
    def test_ignore_already_paid_marks_only_paid_matches_processed(self):
        self.make_invoice("AA-1", status="paid")
        self.make_invoice("BB-1", status="sent")
        paid = self.make_transaction("AA-1")
        unpaid = self.make_transaction("BB-1")

        self.assertEqual(ignore_already_paid(practice=self.practice), 1)

        paid.refresh_from_db()
        unpaid.refresh_from_db()
        self.assertEqual((paid.match_confidence, paid.processed), (Confidence.IGNORED, True))
        self.assertIn("AA-1", paid.notes)
        self.assertEqual((unpaid.match_confidence, unpaid.processed), (Confidence.UNMATCHED, False))

    def test_ignore_unmatched_expenses_only_leaves_incoming_payments(self):
        expense = self.make_transaction("", amount="-10.00")
        income = self.make_transaction("", amount="10.00")

        self.assertEqual(ignore_unmatched(practice=self.practice, expenses_only=True), 1)

        expense.refresh_from_db()
        income.refresh_from_db()
        self.assertEqual((expense.match_confidence, expense.processed), (Confidence.IGNORED, True))
        self.assertEqual(income.match_confidence, Confidence.UNMATCHED)

    def test_ignore_unmatched_is_limited_to_the_practice(self):
        other = self.make_transaction("")
        BankTransaction.objects.filter(pk=other.pk).update(practice=self.other)

        self.assertEqual(ignore_unmatched(practice=self.practice, expenses_only=False), 0)
        other.refresh_from_db()
        self.assertEqual(other.match_confidence, Confidence.UNMATCHED)
