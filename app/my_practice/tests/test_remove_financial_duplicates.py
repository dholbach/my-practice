"""
Tests for the remove_financial_duplicates management command.
"""

from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from ..models import CompanyExpense, CompanyWithdrawal, Practice


class RemoveFinancialDuplicatesTest(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="dup-cmd",
            title="Test Practitioner",
            email="test@practice.example",
            city="Berlin",
        )

    def _make_expense(
        self, *, day=1, amount="50.00", description="Duplicate entry", category="other"
    ):
        return CompanyExpense.objects.create(
            practice=self.practice,
            date=date(2025, 1, day),
            amount=Decimal(amount),
            description=description,
            category=category,
        )

    def _make_withdrawal(
        self, *, day=1, amount="50.00", description="Duplicate entry", category="other"
    ):
        return CompanyWithdrawal.objects.create(
            practice=self.practice,
            date=date(2025, 1, day),
            amount=Decimal(amount),
            description=description,
            category=category,
        )

    def _run(self, *args):
        out = StringIO()
        call_command("remove_financial_duplicates", *args, stdout=out)
        return out.getvalue()

    def test_no_duplicates_reports_success(self):
        self._make_expense(day=1)
        self._make_expense(day=2)  # different date, not a duplicate

        output = self._run("--yes")

        self.assertIn("No duplicates found", output)
        self.assertEqual(CompanyExpense.objects.count(), 2)

    def test_dry_run_does_not_delete(self):
        self._make_expense()
        self._make_expense()

        output = self._run("--dry-run")

        self.assertIn("DRY RUN", output)
        self.assertEqual(CompanyExpense.objects.count(), 2)

    def test_without_yes_flag_aborts_in_non_interactive_mode(self):
        self._make_expense()
        self._make_expense()

        output = self._run()

        self.assertIn("Aborted", output)
        self.assertEqual(CompanyExpense.objects.count(), 2)

    def test_yes_flag_deletes_duplicates_keeping_lowest_id(self):
        first = self._make_expense(category="miete")
        self._make_expense(category="telefon")
        self._make_expense(category="software")

        output = self._run("--yes")

        self.assertIn("Deleted 2 expense duplicates", output)
        self.assertEqual(CompanyExpense.objects.count(), 1)
        remaining = CompanyExpense.objects.first()
        self.assertEqual(remaining.pk, first.pk)
        self.assertEqual(remaining.category, "miete")

    def test_year_filter_scopes_deletion(self):
        self._make_expense(day=1)  # 2025 duplicate pair
        self._make_expense(day=1)
        for _ in range(2):  # 2024 duplicate pair, left untouched by --year 2025
            CompanyExpense.objects.create(
                practice=self.practice,
                date=date(2024, 1, 1),
                amount=Decimal("50.00"),
                description="Duplicate entry",
                category="other",
            )

        self._run("--yes", "--year", "2025")

        self.assertEqual(CompanyExpense.objects.filter(date__year=2025).count(), 1)
        self.assertEqual(CompanyExpense.objects.filter(date__year=2024).count(), 2)

    def test_type_filter_expenses_only_leaves_withdrawals_untouched(self):
        self._make_expense()
        self._make_expense()
        self._make_withdrawal()
        self._make_withdrawal()

        self._run("--yes", "--type", "expenses")

        self.assertEqual(CompanyExpense.objects.count(), 1)
        self.assertEqual(CompanyWithdrawal.objects.count(), 2)

    def test_type_filter_withdrawals_only_leaves_expenses_untouched(self):
        self._make_expense()
        self._make_expense()
        self._make_withdrawal()
        self._make_withdrawal()

        self._run("--yes", "--type", "withdrawals")

        self.assertEqual(CompanyExpense.objects.count(), 2)
        self.assertEqual(CompanyWithdrawal.objects.count(), 1)
