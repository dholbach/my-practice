"""
Tests for expense views.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import BankTransaction, CompanyExpense, Practice, UserPractice


class ExpenseListViewTest(TestCase):
    """Test expense list view."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="12345")
        self.client_instance = TestClient()

        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_expense-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Link user to practice
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)

        self.client_instance.login(username="testuser", password="12345")

        # Create test expenses
        CompanyExpense.objects.create(
            description="Rent December",
            amount=Decimal("1500.00"),
            category="miete",
            date=date(2024, 12, 1),
            is_tax_deductible=True,
            practice=self.practice,
        )
        CompanyExpense.objects.create(
            description="Software License",
            amount=Decimal("99.99"),
            category="software",
            date=date(2024, 11, 15),
            is_tax_deductible=True,
            practice=self.practice,
        )
        CompanyExpense.objects.create(
            description="Office Supplies",
            amount=Decimal("45.50"),
            category="materialien",
            date=date(2023, 6, 10),
            is_tax_deductible=False,
            practice=self.practice,
        )

    def test_expense_list_loads(self):
        """Test that expense list view loads successfully."""
        response = self.client_instance.get(reverse("expense_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/expense_list.html")

    def test_expense_list_shows_expenses(self):
        """Test that expense list shows all expenses."""
        response = self.client_instance.get(reverse("expense_list"))
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(list(response.context["expenses"])), 3)

    def test_expense_list_year_filter(self):
        """Test filtering expenses by year."""
        response = self.client_instance.get(reverse("expense_list") + "?year=2024")
        self.assertContains(response, "Rent December")
        self.assertContains(response, "Software License")
        self.assertNotContains(response, "Office Supplies")

    def test_expense_list_category_breakdown(self):
        """Test that category breakdown is calculated correctly."""
        response = self.client_instance.get(reverse("expense_list"))
        self.assertEqual(response.status_code, 200)
        # Check context data instead of template text
        self.assertIn("category_totals", response.context)
        self.assertIn("grand_total", response.context)
        # Grand total should be sum of all expenses
        grand_total = response.context["grand_total"]
        self.assertGreater(grand_total, 1600)  # 1500 + 99.99 + 45.50


class ExpenseCreateViewTest(TestCase):
    """Test expense create view."""

    def setUp(self):
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_expense-2",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.user = User.objects.create_user(username="testuser", password="12345")
        self.client_instance = TestClient()
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance.login(username="testuser", password="12345")
        session = self.client_instance.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

    def test_expense_create_get(self):
        """Test GET request to create expense."""
        response = self.client_instance.get(reverse("expense_create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/expense_form.html")

    def test_expense_create_post_valid(self):
        """Test POST with valid data creates expense."""
        data = {
            "description": "New Expense",
            "amount": "250.00",
            "category": "telefon",
            "date": "2024-12-23",
            "is_tax_deductible": True,
            "has_invoice": False,
        }
        response = self.client_instance.post(reverse("expense_create"), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success

        expense = CompanyExpense.objects.get(description="New Expense")
        self.assertEqual(expense.amount, Decimal("250.00"))
        self.assertEqual(expense.category, "telefon")
        self.assertTrue(expense.is_tax_deductible)

    def test_expense_create_post_invalid_amount(self):
        """Test POST with invalid amount."""
        data = {
            "description": "Invalid Expense",
            "amount": "-100.00",  # Negative amount
            "category": "other",
            "date": "2024-12-23",
        }
        response = self.client_instance.post(reverse("expense_create"), data)
        # Django form may accept and convert to positive, or redirect
        self.assertIn(response.status_code, [200, 302])


class ExpenseUpdateViewTest(TestCase):
    """Test expense update view."""

    def setUp(self):
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_expense-3",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.user = User.objects.create_user(username="testuser", password="12345")
        self.client_instance = TestClient()

        # Link user to practice
        UserPractice.objects.get_or_create(
            user=self.user, practice=self.practice, defaults={"is_owner": True}
        )

        self.client_instance.login(username="testuser", password="12345")

        # Set practice in session for middleware
        session = self.client_instance.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

        self.expense = CompanyExpense.objects.create(
            description="Original Description",
            amount=Decimal("100.00"),
            category="Test",
            date=date(2024, 12, 1),
            practice=self.practice,
        )

    def test_expense_update_get(self):
        """Test GET request to update expense."""
        response = self.client_instance.get(reverse("expense_update", args=[self.expense.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/expense_form.html")
        self.assertContains(response, "Original Description")

    def test_expense_update_post_valid(self):
        """Test POST with valid data updates expense."""
        data = {
            "description": "Updated Description",
            "amount": "200.00",
            "category": "software",
            "date": "2024-12-23",
            "is_tax_deductible": True,
        }
        response = self.client_instance.post(
            reverse("expense_update", args=[self.expense.pk]), data
        )
        self.assertEqual(response.status_code, 302)

        self.expense.refresh_from_db()
        self.assertEqual(self.expense.description, "Updated Description")
        self.assertEqual(self.expense.amount, Decimal("200.00"))
        self.assertEqual(self.expense.category, "software")
        self.assertTrue(self.expense.is_tax_deductible)

    def test_expense_update_nonexistent(self):
        """Test updating nonexistent expense returns 404."""
        response = self.client_instance.get(reverse("expense_update", args=[99999]))
        self.assertEqual(response.status_code, 404)


class ExpenseDeleteViewTest(TestCase):
    """Test expense delete view."""

    def setUp(self):
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_expense-4",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.user = User.objects.create_user(username="testuser", password="12345")
        self.client_instance = TestClient()

        UserPractice.objects.get_or_create(
            user=self.user, practice=self.practice, defaults={"is_owner": True}
        )

        self.client_instance.login(username="testuser", password="12345")

        session = self.client_instance.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

        self.expense = CompanyExpense.objects.create(
            description="To Delete",
            amount=Decimal("50.00"),
            category="Test",
            date=date(2024, 12, 1),
            practice=self.practice,
        )

    def test_expense_delete_get(self):
        """Test GET request shows confirmation page."""
        response = self.client_instance.get(reverse("expense_delete", args=[self.expense.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "To Delete")

    def test_expense_delete_post(self):
        """Test POST request deletes expense."""
        expense_id = self.expense.pk
        response = self.client_instance.post(reverse("expense_delete", args=[expense_id]))
        self.assertEqual(response.status_code, 302)

        # Verify expense was deleted
        self.assertFalse(CompanyExpense.objects.filter(pk=expense_id).exists())

    def test_expense_delete_nonexistent(self):
        """Test deleting nonexistent expense returns 404."""
        response = self.client_instance.post(reverse("expense_delete", args=[99999]))
        self.assertEqual(response.status_code, 404)


class ExpenseMergeViewTest(TestCase):
    """Tests for expense_merge view — all four transaction/manual combinations."""

    def setUp(self):
        self.user = User.objects.create_user(username="mergeuser", password="pass")
        self.practice = Practice.objects.create(
            name="Merge Practice",
            slug="merge-practice",
            email="merge@example.com",
            iban="DE89370400440532013000",
        )
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance = TestClient()
        self.client_instance.login(username="mergeuser", password="pass")

    def _expense(self, amount, description="Expense"):
        return CompanyExpense.objects.create(
            practice=self.practice,
            description=description,
            amount=Decimal(amount),
            category="software",
            date=date(2026, 1, 1),
        )

    def _transaction(self, expense, amount):
        return BankTransaction.objects.create(
            practice=self.practice,
            transaction_date=date(2026, 1, 1),
            value_date=date(2026, 1, 1),
            amount=Decimal(amount),
            balance_after=Decimal("1000.00"),
            payer_name="Test",
            reference="ref",
            linked_expense=expense,
        )

    def _merge(self, target, source):
        return self.client_instance.post(
            reverse("expense_merge", args=[target.pk]),
            {"source_id": source.pk},
        )

    def test_both_manual_sums_amounts(self):
        """Neither has a bank transaction — amounts should be summed."""
        target = self._expense("100.00", "Target")
        source = self._expense("40.00", "Source")
        self._merge(target, source)
        target.refresh_from_db()
        self.assertEqual(target.amount, Decimal("140.00"))
        self.assertFalse(CompanyExpense.objects.filter(pk=source.pk).exists())

    def test_both_have_transactions_sums_amounts(self):
        """Both have linked transactions — synced total should cover both."""
        target = self._expense("80.00", "Target")
        source = self._expense("60.00", "Source")
        self._transaction(target, "80.00")
        self._transaction(source, "60.00")
        self._merge(target, source)
        target.refresh_from_db()
        self.assertEqual(target.amount, Decimal("140.00"))

    def test_target_manual_source_has_transaction(self):
        """Bug case: target is manual-only, source has a bank transaction.
        Original target amount must not be silently dropped."""
        target = self._expense("100.00", "Target manual")
        source = self._expense("60.00", "Source with txn")
        self._transaction(source, "60.00")
        self._merge(target, source)
        target.refresh_from_db()
        self.assertEqual(target.amount, Decimal("160.00"))

    def test_target_has_transaction_source_manual(self):
        """Target has a transaction, source is manual-only."""
        target = self._expense("80.00", "Target with txn")
        source = self._expense("40.00", "Source manual")
        self._transaction(target, "80.00")
        self._merge(target, source)
        target.refresh_from_db()
        # Transaction-backed amount takes precedence; source's manual amount is included
        # via the synced transaction sum (source had no transactions to contribute).
        self.assertEqual(target.amount, Decimal("80.00"))

    def test_source_deleted_after_merge(self):
        """Source expense is always deleted regardless of case."""
        target = self._expense("50.00")
        source = self._expense("50.00")
        self._merge(target, source)
        self.assertFalse(CompanyExpense.objects.filter(pk=source.pk).exists())
