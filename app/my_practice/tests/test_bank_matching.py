"""Tests for bank_matching: recording a payment all-or-nothing, and payer aliases."""

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
from ..utils.bank_matching import (
    InvoiceNotPayableError,
    create_payer_alias,
    payer_needs_alias,
    record_payment,
)
from .test_helpers import create_test_practice, mark_paid_fails_for


class BankMatchingBase(TestCase):
    def setUp(self):
        self.practice = create_test_practice(slug="bank-matching-1")
        self._rows = 0

    @allow_issued_invoice_writes()
    def make_invoice(self, number, invoice_date=date(2026, 1, 1), payer="Max Mustermann"):
        client = Client.objects.create(
            practice=self.practice, full_name=payer, client_code=number.split("-")[0]
        )
        invoice = Invoice.objects.create(
            practice=self.practice,
            client=client,
            invoice_number=number,
            status="sent",
            invoice_date=date(2026, 1, 1),
        )
        service_type, _ = ServiceType.objects.get_or_create(
            code="test_therapy_60", defaults={"practice": self.practice, "name": "Therapy 60min"}
        )
        session = Session.objects.create(client=client, session_date=date(2026, 1, 1), duration=60)
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=service_type,
            session=session,
            rate=Decimal("90.00"),
            quantity=1,
        )
        Invoice.objects.filter(pk=invoice.pk).update(invoice_date=invoice_date)
        invoice.refresh_from_db()
        return invoice

    def make_transaction(self, payer="Jemand", day=date(2026, 1, 15)):
        self._rows += 1
        return BankTransaction.objects.create(
            practice=self.practice,
            transaction_date=day,
            value_date=day,
            payer_name=payer,
            payer_iban="",
            reference=f"ref {self._rows}",
            amount=Decimal("90.00"),
            balance_after=Decimal("1000.00"),
            account_iban="DE89370400440532013000",
            match_confidence="unmatched",
            processed=False,
        )


class RecordPaymentTests(BankMatchingBase):
    def test_marks_invoices_paid_on_the_transaction_date_and_links_the_first(self):
        first = self.make_invoice("AA-1")
        second = self.make_invoice("BB-2")
        transaction = self.make_transaction()
        record_payment(transaction, [first, second], confidence="manual", notes="two invoices")

        for invoice in (first, second):
            invoice.refresh_from_db()
            self.assertEqual((invoice.status, invoice.paid_date), ("paid", date(2026, 1, 15)))
        transaction.refresh_from_db()
        self.assertEqual(transaction.matched_invoice, first)
        self.assertEqual(
            (transaction.match_confidence, transaction.processed, transaction.notes),
            ("manual", True, "two invoices"),
        )

    def test_empty_notes_leave_the_existing_notes_alone(self):
        invoice = self.make_invoice("AA-1")
        transaction = self.make_transaction()
        transaction.notes = "from the import"
        record_payment(transaction, [invoice], confidence="exact")
        transaction.refresh_from_db()
        self.assertEqual(transaction.notes, "from the import")

    def test_nothing_is_written_when_one_invoice_cannot_be_paid(self):
        fine = self.make_invoice("AA-1")
        broken = self.make_invoice("BB-2")
        transaction = self.make_transaction()

        with mark_paid_fails_for("BB-2"), self.assertRaises(InvoiceNotPayableError) as caught:
            record_payment(transaction, [fine, broken], confidence="manual")

        self.assertEqual(caught.exception.invoice, broken)
        self.assertTrue(caught.exception.reasons)
        for invoice in (fine, broken):
            invoice.refresh_from_db()
            self.assertEqual(invoice.status, "sent")
        transaction.refresh_from_db()
        self.assertFalse(transaction.processed)
        self.assertIsNone(transaction.matched_invoice)

    def test_a_transfer_before_the_invoice_date_is_recorded_and_reported(self):
        ahead = self.make_invoice("AA-1", invoice_date=date(2026, 2, 1))
        on_time = self.make_invoice("BB-2")
        transaction = self.make_transaction()

        early = record_payment(transaction, [ahead, on_time], confidence="manual")

        self.assertEqual([invoice.invoice_number for invoice in early], ["AA-1"])
        ahead.refresh_from_db()
        self.assertEqual((ahead.status, ahead.paid_date), ("paid", date(2026, 1, 15)))
        transaction.refresh_from_db()
        self.assertTrue(transaction.processed)

    def test_nothing_is_reported_when_every_payment_follows_its_invoice(self):
        invoice = self.make_invoice("AA-1")
        self.assertEqual(record_payment(self.make_transaction(), [invoice], confidence="exact"), [])

    def test_needs_at_least_one_invoice(self):
        with self.assertRaises(ValueError):
            record_payment(self.make_transaction(), [], confidence="manual")


class PayerAliasTests(BankMatchingBase):
    def test_a_different_payer_name_needs_an_alias(self):
        invoice = self.make_invoice("AA-1")
        self.assertTrue(payer_needs_alias(self.make_transaction(payer="M. Schmidt"), invoice))

    def test_the_clients_own_name_does_not_whatever_its_case_or_spacing(self):
        invoice = self.make_invoice("AA-1")
        self.assertFalse(
            payer_needs_alias(self.make_transaction(payer=" MAX mustermann "), invoice)
        )

    def test_a_missing_payer_name_does_not(self):
        invoice = self.make_invoice("AA-1")
        self.assertFalse(payer_needs_alias(self.make_transaction(payer=""), invoice))

    def test_an_existing_alias_does_not_whatever_its_case(self):
        invoice = self.make_invoice("AA-1")
        ClientAlias.objects.create(client=invoice.client, alias_name="m. schmidt")
        self.assertFalse(payer_needs_alias(self.make_transaction(payer="M. Schmidt"), invoice))

    def test_another_clients_alias_does_not_count(self):
        invoice = self.make_invoice("AA-1")
        other = self.make_invoice("BB-2", payer="Anna Schmidt")
        ClientAlias.objects.create(client=other.client, alias_name="M. Schmidt")
        self.assertTrue(payer_needs_alias(self.make_transaction(payer="M. Schmidt"), invoice))

    def test_create_stores_the_payer_name_and_note_on_the_client(self):
        invoice = self.make_invoice("AA-1")
        alias = create_payer_alias(self.make_transaction(payer="M. Schmidt"), invoice, "a note")
        self.assertEqual(
            (alias.client, alias.alias_name, alias.notes), (invoice.client, "M. Schmidt", "a note")
        )
