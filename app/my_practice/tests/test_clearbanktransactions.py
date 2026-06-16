"""
Tests for the clearbanktransactions management command.

Covers: filter modes (default/--all/--since/--imported-on/--today),
--with-financials, --yes bypass, empty result, invalid date errors.
"""

from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from ..models import BankTransaction, CompanyExpense, CompanyWithdrawal, Practice

PRACTICE_IBAN = "DE89370400440532013000"


def _make_practice(slug="cmd-test"):
    return Practice.objects.create(
        name="Test Praxis",
        slug=slug,
        title="Therapeutin",
        email="test@example.com",
        iban=PRACTICE_IBAN,
    )


def _make_transaction(practice, **kwargs):
    defaults = dict(
        transaction_date=date(2026, 1, 15),
        value_date=date(2026, 1, 15),
        payer_name="Test Zahler",
        payer_iban="",
        reference="Test Überweisung",
        amount=Decimal("90.00"),
        balance_after=Decimal("1090.00"),
        account_iban=PRACTICE_IBAN,
        match_confidence="unmatched",
        processed=False,
    )
    defaults.update(kwargs)
    return BankTransaction.objects.create(practice=practice, **defaults)


def _run(*args):
    """Run the command and return stdout."""
    out = StringIO()
    call_command("clearbanktransactions", *args, "--yes", stdout=out)
    return out.getvalue()


class ClearDefaultModeTest(TestCase):
    """Default mode: deletes only unprocessed transactions."""

    def setUp(self):
        self.practice = _make_practice("cmd-default")

    def test_deletes_unprocessed(self):
        _make_transaction(self.practice, processed=False)
        output = _run()
        self.assertEqual(BankTransaction.objects.count(), 0)
        self.assertIn("deleted", output)

    def test_keeps_processed(self):
        _make_transaction(
            self.practice, processed=True, reference="Processed Ref", match_confidence="manual"
        )
        _run()
        self.assertEqual(BankTransaction.objects.count(), 1)

    def test_no_transactions_prints_error(self):
        out = StringIO()
        call_command("clearbanktransactions", "--yes", stdout=out)
        self.assertIn("No", out.getvalue())


class ClearAllFlagTest(TestCase):
    def setUp(self):
        self.practice = _make_practice("cmd-all")

    def test_deletes_processed_and_unprocessed(self):
        _make_transaction(self.practice, processed=False)
        _make_transaction(
            self.practice, processed=True, reference="Done", match_confidence="manual"
        )
        _run("--all")
        self.assertEqual(BankTransaction.objects.count(), 0)


class ClearSinceDateTest(TestCase):
    def setUp(self):
        self.practice = _make_practice("cmd-since")

    def test_deletes_on_or_after_date(self):
        _make_transaction(self.practice, transaction_date=date(2026, 1, 15), reference="Ref A")
        _make_transaction(self.practice, transaction_date=date(2026, 1, 10), reference="Ref B")
        _run("--since", "2026-01-12")
        # Ref A (Jan 15) deleted; Ref B (Jan 10) kept
        self.assertEqual(BankTransaction.objects.count(), 1)
        self.assertEqual(BankTransaction.objects.first().reference, "Ref B")

    def test_invalid_date_raises(self):
        with self.assertRaises(CommandError):
            call_command("clearbanktransactions", "--since", "not-a-date", "--yes")


class ClearImportedOnTest(TestCase):
    def setUp(self):
        self.practice = _make_practice("cmd-imported-on")

    def test_deletes_imported_today(self):
        # imported_at is auto_now_add so transactions created now have today's date
        _make_transaction(self.practice)
        today_str = date.today().isoformat()
        _run("--imported-on", today_str)
        self.assertEqual(BankTransaction.objects.count(), 0)

    def test_different_date_keeps_transaction(self):
        _make_transaction(self.practice)
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        _run("--imported-on", yesterday_str)
        self.assertEqual(BankTransaction.objects.count(), 1)

    def test_invalid_date_raises(self):
        with self.assertRaises(CommandError):
            call_command("clearbanktransactions", "--imported-on", "32.13.2026", "--yes")


class ClearTodayFlagTest(TestCase):
    def setUp(self):
        self.practice = _make_practice("cmd-today")

    def test_today_deletes_todays_imports(self):
        _make_transaction(self.practice)
        _run("--today")
        self.assertEqual(BankTransaction.objects.count(), 0)


class ClearWithFinancialsTest(TestCase):
    def setUp(self):
        self.practice = _make_practice("cmd-financials")

    def test_since_with_financials_deletes_linked_expense(self):
        expense = CompanyExpense.objects.create(
            practice=self.practice,
            date=date(2026, 1, 15),
            amount=Decimal("120.00"),
            description="Miete",
            category="other",
        )
        trans = _make_transaction(
            self.practice,
            transaction_date=date(2026, 1, 15),
            amount=Decimal("-120.00"),
            reference="Miete Ref",
            match_confidence="auto-expense",
        )
        trans.linked_expense = expense
        trans.save()

        _run("--since", "2026-01-01", "--with-financials")

        self.assertEqual(BankTransaction.objects.count(), 0)
        self.assertFalse(CompanyExpense.objects.filter(id=expense.id).exists())

    def test_since_with_financials_deletes_linked_withdrawal(self):
        wd = CompanyWithdrawal.objects.create(
            practice=self.practice,
            date=date(2026, 1, 15),
            amount=Decimal("500.00"),
            description="Entnahme",
            category="salary",
        )
        trans = _make_transaction(
            self.practice,
            transaction_date=date(2026, 1, 15),
            amount=Decimal("-500.00"),
            reference="Entnahme Ref",
            match_confidence="auto-withdrawal",
        )
        trans.linked_withdrawal = wd
        trans.save()

        _run("--since", "2026-01-01", "--with-financials")

        self.assertEqual(BankTransaction.objects.count(), 0)
        self.assertFalse(CompanyWithdrawal.objects.filter(id=wd.id).exists())

    def test_imported_on_with_financials_uses_created_at(self):
        expense = CompanyExpense.objects.create(
            practice=self.practice,
            date=date(2026, 1, 15),
            amount=Decimal("120.00"),
            description="Same-day import expense",
            category="other",
        )
        _make_transaction(self.practice, reference="Some import")
        today_str = date.today().isoformat()

        _run("--imported-on", today_str, "--with-financials")

        self.assertEqual(BankTransaction.objects.count(), 0)
        # Expense was created today → should be deleted too
        self.assertFalse(CompanyExpense.objects.filter(id=expense.id).exists())
