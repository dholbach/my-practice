"""
Tests for the company finance models: withdrawals and expenses.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from my_practice.models import (
    CompanyExpense,
    CompanyWithdrawal,
)

from .test_helpers import create_test_practice


class CompanyWithdrawalModelTestCase(TestCase):
    """Tests for CompanyWithdrawal model"""

    def setUp(self):
        """Create test practice"""
        self.practice = create_test_practice(name="Test Practice", slug="models-withdrawal")

    def test_withdrawal_creation(self):
        """Test creating a withdrawal"""
        withdrawal = CompanyWithdrawal.objects.create(
            date=date.today(),
            amount=Decimal("1000.00"),
            description="Test withdrawal",
            practice=self.practice,
        )
        self.assertEqual(withdrawal.amount, Decimal("1000.00"))

    def test_withdrawal_str(self):
        """Test CompanyWithdrawal string representation"""
        withdrawal = CompanyWithdrawal.objects.create(
            date=date(2025, 12, 24), amount=Decimal("500.00"), practice=self.practice
        )
        # Check it contains key info
        self.assertIn("500", str(withdrawal))
        self.assertIn("2025", str(withdrawal))

    def test_withdrawal_ordering(self):
        """Test withdrawal ordering (newest first)"""
        CompanyWithdrawal.objects.create(
            date=date(2025, 1, 1), amount=Decimal("100.00"), practice=self.practice
        )
        CompanyWithdrawal.objects.create(
            date=date(2025, 12, 1), amount=Decimal("200.00"), practice=self.practice
        )

        withdrawals = list(CompanyWithdrawal.objects.all())
        self.assertEqual(withdrawals[0].date, date(2025, 12, 1))


class CompanyExpenseModelTestCase(TestCase):
    """Tests for CompanyExpense model"""

    def setUp(self):
        """Create test practice"""
        self.practice = create_test_practice(name="Test Practice", slug="models-expense")

    def test_expense_creation(self):
        """Test creating an expense"""
        expense = CompanyExpense.objects.create(
            date=date.today(),
            description="Test expense",
            category="supplies",
            amount=Decimal("50.00"),
            practice=self.practice,
        )
        self.assertEqual(expense.category, "supplies")
        self.assertEqual(expense.amount, Decimal("50.00"))

    def test_expense_str(self):
        """Test CompanyExpense string representation"""
        expense = CompanyExpense.objects.create(
            date=date(2025, 12, 24),
            description="Office supplies",
            category="supplies",
            amount=Decimal("75.50"),
            practice=self.practice,
        )
        # Check it contains key info
        result = str(expense)
        self.assertTrue("Office" in result or "supplies" in result or "75" in result)

    def test_expense_defaults(self):
        """Test CompanyExpense default values"""
        expense = CompanyExpense.objects.create(
            date=date.today(),
            description="Test",
            category="other",
            amount=Decimal("10.00"),
            practice=self.practice,
        )
        self.assertTrue(expense.is_tax_deductible)
        self.assertFalse(expense.has_invoice)
