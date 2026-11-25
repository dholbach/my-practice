"""
Tests for the bank review view: listing, paging, bulk and single actions, matching and aliases.
"""

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.urls import reverse
from django.utils import translation

from ..models import (
    BankTransaction,
    Client,
    ClientAlias,
    Invoice,
)
from .bank_import_helpers import PRACTICE_IBAN, BankImportViewBase, make_invoice_item
from .test_helpers import mark_paid_fails_for


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
        make_invoice_item(invoice, self.practice, client_obj, rate=total)
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

    def test_payer_name_known_when_matches_client_full_name(self):
        Client.objects.create(practice=self.practice, full_name="Anna Schmidt", client_code="AS-1")
        self._make_unmatched(payer="anna schmidt")  # case-insensitive match
        response = self.http.get(reverse("bank_review"))
        transaction = response.context["transactions"][0]
        self.assertTrue(transaction.payer_name_known)
        self.assertNotContains(response, "create_alias")

    def test_payer_name_known_when_alias_exists(self):
        client_obj = Client.objects.create(
            practice=self.practice, full_name="Anna Schmidt", client_code="AS-1"
        )
        ClientAlias.objects.create(client=client_obj, alias_name="A. Schmidt (Mutter)")
        self._make_unmatched(payer="a. schmidt (mutter)")
        response = self.http.get(reverse("bank_review"))
        transaction = response.context["transactions"][0]
        self.assertTrue(transaction.payer_name_known)
        self.assertNotContains(response, "create_alias")

    def test_payer_name_unknown_offers_alias_checkbox(self):
        Client.objects.create(practice=self.practice, full_name="Anna Schmidt", client_code="AS-1")
        self._make_unmatched(payer="Hans Mueller")
        response = self.http.get(reverse("bank_review"))
        transaction = response.context["transactions"][0]
        self.assertFalse(transaction.payer_name_known)
        self.assertContains(response, "create_alias")


class BankReviewDataAmountTest(BankReviewViewBase):
    """data-amount feeds parseFloat in bank_review.js, so it must not be localized.

    Django localizes template numbers, and LANGUAGE_CODE is "de-de" — a bare
    {{ trans.amount }} renders "90,50", which parseFloat truncates to 90. That
    silently drops the cents from the tally's match comparison, so a transaction
    that exactly matches its invoice was reported as a 0,50 € mismatch. The
    template uses |unlocalize; this pins it.
    """

    def test_data_amount_is_a_machine_readable_decimal(self):
        self._make_unmatched(amount="90,50")
        with translation.override("de"):
            response = self.http.get(reverse("bank_review"))
        self.assertContains(response, 'data-amount="90.50"')
        self.assertNotContains(response, 'data-amount="90,50"')

    def test_data_amount_has_no_thousands_separator(self):
        self._make_unmatched(amount="1234,56")
        with translation.override("de"):
            response = self.http.get(reverse("bank_review"))
        self.assertContains(response, 'data-amount="1234.56"')


class BankReviewPaginationTest(BankReviewViewBase):
    def test_paid_invoice_count_includes_matches_beyond_first_page(self):
        """paid_invoice_count must count matches across all pages, not just page 1 (20/page)."""
        # 20 unrelated unmatched transactions, sorted after the match by -transaction_date
        # (later date = earlier page), so the paid match (transaction 21) lands on page 2.
        for i in range(20):
            self._make_unmatched(ref=f"Filler {i}", payer=f"Filler {i}")
        self._make_invoice(number="PG-1", status="paid", total=Decimal("90.00"), payer="Page Payer")
        trans = self._make_unmatched(ref="PG-1", amount="90,00", payer="Page Payer")
        trans.extracted_invoice_number = "PG-1"
        trans.transaction_date = date(2026, 1, 1)  # oldest -> sorts onto page 2
        trans.value_date = date(2026, 1, 1)
        trans.save()

        response = self.http.get(reverse("bank_review"))
        self.assertEqual(response.context["page_obj"].number, 1)
        self.assertEqual(len(response.context["transactions"]), 20)
        self.assertEqual(response.context["paid_invoice_count"], 1)


class BankReviewBulkActionsTest(BankReviewViewBase):
    def test_ignore_all_unmatched(self):
        self._make_unmatched(ref="Ref A")
        self._make_unmatched(ref="Ref B")
        response = self.http.post(reverse("bank_review"), {"action": "ignore_all_unmatched"})
        self.assertRedirects(response, reverse("bank_review"))
        self.assertEqual(BankTransaction.objects.filter(match_confidence="ignored").count(), 2)
        self.assertFalse(BankTransaction.objects.filter(processed=False).exists())

    def test_ignore_all_expenses(self):
        self._make_unmatched(ref="Expense", amount="-120,00")
        self._make_unmatched(ref="Income", amount="90,00")  # positive, should NOT be ignored
        self.http.post(reverse("bank_review"), {"action": "ignore_all_expenses"})
        ignored = BankTransaction.objects.filter(match_confidence="ignored")
        self.assertEqual(ignored.count(), 1)
        self.assertEqual(ignored.first().reference, "Expense")
        self.assertTrue(ignored.first().processed)
        self.assertEqual(self.http.get(reverse("bank_review")).context["expense_count"], 0)

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

    def test_auto_match_rejects_amount_mismatch(self):
        # suggested_invoice_id is a hidden field; the server re-checks the amount.
        invoice = self._make_invoice(
            number="AX-1", status="sent", total=Decimal("90.00"), payer="Amount Check"
        )
        trans = self._make_unmatched(ref="AX-1", amount="10,00")
        self.http.post(
            reverse("bank_review"),
            {
                "action": "auto_match",
                "transaction_id": trans.id,
                "suggested_invoice_id": invoice.id,
            },
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "sent")
        trans.refresh_from_db()
        self.assertIsNone(trans.matched_invoice)

    def test_auto_match_marks_transaction_processed(self):
        invoice = self._make_invoice(
            number="AP-1", status="sent", total=Decimal("90.00"), payer="Processed Check"
        )
        trans = self._make_unmatched(ref="AP-1", amount="90,00")
        self.http.post(
            reverse("bank_review"),
            {
                "action": "auto_match",
                "transaction_id": trans.id,
                "suggested_invoice_id": invoice.id,
            },
        )
        trans.refresh_from_db()
        self.assertTrue(trans.processed)

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


class BankReviewStoredNotesTest(BankReviewViewBase):
    """Notes the review writes to the database follow the user's language."""

    def _match_two(self, language):
        self.http.cookies[settings.LANGUAGE_COOKIE_NAME] = language
        first = self._make_invoice(number="CN-1", payer="Max Mustermann")
        second = self._make_invoice(number="CO-2", payer="Max Mustermann")
        trans = self._make_unmatched(ref="CN-1 CO-2", amount="180,00", payer="M. Schmidt")
        self.http.post(
            reverse("bank_review"),
            {
                "action": "match",
                "transaction_id": trans.id,
                "invoice": [first.id, second.id],
                "create_alias": "1",
            },
        )
        trans.refresh_from_db()
        alias = ClientAlias.objects.get(alias_name="M. Schmidt")
        return trans.notes, alias.notes

    def test_notes_in_german(self):
        payment_note, alias_note = self._match_two("de")
        self.assertEqual(payment_note, "Sammelzahlung für: CN-1, CO-2")
        self.assertEqual(alias_note, "Angelegt beim Bankimport vom 15.01.2026")

    def test_notes_in_english(self):
        payment_note, alias_note = self._match_two("en")
        self.assertEqual(payment_note, "Combined payment for: CN-1, CO-2")
        self.assertIn("Created during the bank import of", alias_note)


class BankReviewMatchTest(BankReviewViewBase):
    """Matching one transaction to invoices: what is marked paid, and what is all-or-nothing."""

    def _post(self, trans, **extra):
        return self.http.post(
            reverse("bank_review"),
            {"transaction_id": trans.id, **extra},
        )

    def _date_invoice(self, invoice, day):
        Invoice.objects.filter(pk=invoice.pk).update(invoice_date=day)

    def test_match_marks_every_invoice_paid_and_links_the_newest_first(self):
        older = self._make_invoice(number="MA-1", payer="Max Mustermann")
        newer = self._make_invoice(number="MB-2", payer="Max Mustermann")
        self._date_invoice(older, date(2026, 1, 2))
        self._date_invoice(newer, date(2026, 1, 9))
        trans = self._make_unmatched(ref="MA-1 MB-2", amount="180,00")
        self._post(trans, action="match", invoice=[older.id, newer.id])

        for invoice in (older, newer):
            invoice.refresh_from_db()
            self.assertEqual((invoice.status, invoice.paid_date), ("paid", date(2026, 1, 15)))
        trans.refresh_from_db()
        self.assertEqual(trans.matched_invoice, newer)
        self.assertEqual(trans.match_confidence, "manual")
        self.assertTrue(trans.processed)

    def test_match_with_equal_dates_lists_invoices_by_number(self):
        second = self._make_invoice(number="MD-2", payer="Max Mustermann")
        first = self._make_invoice(number="MC-1", payer="Max Mustermann")
        trans = self._make_unmatched(ref="MC-1 MD-2", amount="180,00")
        self._post(trans, action="match", invoice=[second.id, first.id])
        trans.refresh_from_db()
        self.assertEqual(trans.matched_invoice, first)

    def test_match_is_all_or_nothing_when_one_invoice_cannot_be_paid(self):
        fine = self._make_invoice(number="ME-1", payer="Max Mustermann")
        broken = self._make_invoice(number="MF-2", payer="Max Mustermann")
        trans = self._make_unmatched(ref="ME-1 MF-2", amount="180,00")
        with mark_paid_fails_for("MF-2"):
            self._post(trans, action="match", invoice=[fine.id, broken.id])

        for invoice in (fine, broken):
            invoice.refresh_from_db()
            self.assertEqual(invoice.status, "sent")
        trans.refresh_from_db()
        self.assertFalse(trans.processed)
        self.assertEqual(trans.match_confidence, "unmatched")

    def test_match_without_an_invoice_changes_nothing(self):
        trans = self._make_unmatched(ref="nothing selected")
        self._post(trans, action="match")
        trans.refresh_from_db()
        self.assertFalse(trans.processed)
        self.assertIsNone(trans.matched_invoice)

    def test_match_stores_the_notes(self):
        invoice = self._make_invoice(number="MG-1", payer="Max Mustermann")
        trans = self._make_unmatched(ref="MG-1")
        self._post(trans, action="match", invoice=[invoice.id], notes="paid in cash")
        trans.refresh_from_db()
        self.assertEqual(trans.notes, "paid in cash")

    def test_auto_match_is_refused_when_the_invoice_cannot_be_paid(self):
        invoice = self._make_invoice(number="MH-1", payer="Max Mustermann")
        trans = self._make_unmatched(ref="MH-1", amount="90,00")
        with mark_paid_fails_for("MH-1"):
            self._post(trans, action="auto_match", suggested_invoice_id=invoice.id)
        invoice.refresh_from_db()
        trans.refresh_from_db()
        self.assertEqual(invoice.status, "sent")
        self.assertFalse(trans.processed)

    def _post_following(self, trans, **extra):
        return self.http.post(
            reverse("bank_review"), {"transaction_id": trans.id, **extra}, follow=True
        )

    def test_match_before_the_invoice_date_is_recorded_with_a_warning(self):
        invoice = self._make_invoice(number="MI-1", payer="Max Mustermann")
        self._date_invoice(invoice, date(2026, 2, 1))  # after the payment date
        trans = self._make_unmatched(ref="MI-1", amount="90,00")
        response = self._post_following(trans, action="match", invoice=[invoice.id])

        invoice.refresh_from_db()
        trans.refresh_from_db()
        self.assertEqual((invoice.status, invoice.paid_date), ("paid", date(2026, 1, 15)))
        self.assertTrue(trans.processed)
        warnings = [m for m in response.context["messages"] if m.level_tag == "warning"]
        self.assertEqual(len(warnings), 1)
        self.assertIn("MI-1", warnings[0].message)

    def test_auto_match_before_the_invoice_date_is_recorded_with_a_warning(self):
        invoice = self._make_invoice(number="MJ-1", payer="Max Mustermann")
        self._date_invoice(invoice, date(2026, 2, 1))
        trans = self._make_unmatched(ref="MJ-1", amount="90,00")
        response = self._post_following(trans, action="auto_match", suggested_invoice_id=invoice.id)

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")
        warnings = [m for m in response.context["messages"] if m.level_tag == "warning"]
        self.assertEqual(len(warnings), 1)

    def test_a_payment_after_the_invoice_date_raises_no_warning(self):
        invoice = self._make_invoice(number="MK-1", payer="Max Mustermann")
        trans = self._make_unmatched(ref="MK-1", amount="90,00")
        response = self._post_following(trans, action="match", invoice=[invoice.id])
        self.assertFalse([m for m in response.context["messages"] if m.level_tag == "warning"])


class BankReviewAliasTest(BankReviewViewBase):
    """A payer name that differs from the client's is remembered as an alias, once."""

    def setUp(self):
        super().setUp()
        self.http.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

    def _confirm(self, invoice, payer):
        trans = self._make_unmatched(ref=f"{invoice.invoice_number} Zahlung", payer=payer)
        self.http.post(
            reverse("bank_review"),
            {
                "action": "confirm_paid",
                "transaction_id": trans.id,
                "suggested_invoice_id": invoice.id,
            },
        )
        return trans

    def _match(self, invoice, payer, create_alias):
        trans = self._make_unmatched(ref=f"{invoice.invoice_number} Zahlung", payer=payer)
        data = {"action": "match", "transaction_id": trans.id, "invoice": [invoice.id]}
        if create_alias:
            data["create_alias"] = "1"
        self.http.post(reverse("bank_review"), data)
        return trans

    def test_confirming_creates_an_alias_with_a_confirm_note(self):
        invoice = self._make_invoice(number="AL-1", status="paid", payer="Max Mustermann")
        self._confirm(invoice, payer="M. Schmidt")
        alias = ClientAlias.objects.get(client=invoice.client)
        self.assertEqual(alias.alias_name, "M. Schmidt")
        self.assertIn("Created automatically on confirming the payment of", alias.notes)

    def test_matching_with_the_box_ticked_creates_an_alias_with_an_import_note(self):
        invoice = self._make_invoice(number="AL-2", payer="Max Mustermann")
        self._match(invoice, payer="M. Schmidt", create_alias=True)
        alias = ClientAlias.objects.get(client=invoice.client)
        self.assertIn("Created during the bank import of", alias.notes)

    def test_matching_without_the_box_creates_no_alias(self):
        invoice = self._make_invoice(number="AL-3", payer="Max Mustermann")
        self._match(invoice, payer="M. Schmidt", create_alias=False)
        self.assertFalse(ClientAlias.objects.exists())

    def test_the_clients_own_name_is_no_alias_whatever_its_case(self):
        invoice = self._make_invoice(number="AL-4", status="paid", payer="Max Mustermann")
        self._confirm(invoice, payer="  MAX MUSTERMANN ")
        self.assertFalse(ClientAlias.objects.exists())

    def test_an_existing_alias_is_not_created_twice(self):
        invoice = self._make_invoice(number="AL-5", status="paid", payer="Max Mustermann")
        ClientAlias.objects.create(client=invoice.client, alias_name="m. schmidt")
        self._confirm(invoice, payer="M. Schmidt")
        self.assertEqual(ClientAlias.objects.filter(client=invoice.client).count(), 1)

    def test_a_transaction_without_a_payer_name_creates_no_alias(self):
        invoice = self._make_invoice(number="AL-6", status="paid", payer="Max Mustermann")
        self._confirm(invoice, payer="")
        self.assertFalse(ClientAlias.objects.exists())

    def test_confirming_without_an_invoice_still_confirms_the_transaction(self):
        trans = self._make_unmatched(ref="no invoice")
        self.http.post(
            reverse("bank_review"), {"action": "confirm_paid", "transaction_id": trans.id}
        )
        trans.refresh_from_db()
        self.assertEqual((trans.match_confidence, trans.processed), ("manual", True))
        self.assertIsNone(trans.matched_invoice)
        self.assertFalse(ClientAlias.objects.exists())
