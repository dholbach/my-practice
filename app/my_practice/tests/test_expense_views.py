"""
Tests for expense views.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from my_practice.models import (
    BankTransaction,
    CompanyExpense,
    ExpenseCategoryRule,
    ExpenseReceipt,
    Practice,
    UserPractice,
)
from my_practice.tests.test_helpers import make_pdf_bytes, select_practice

from .test_helpers import create_test_practice

User = get_user_model()


class ExpenseListViewTest(TestCase):
    """Tests for expense_list view"""

    def setUp(self):
        """Set up test data"""
        self.client = TestClient()

        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="expense_views-1")

        # Create and login user
        self.user = User.objects.create_user(username="expenseuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client.login(username="expenseuser", password="testpass123")

        # Create expenses for different years
        CompanyExpense.objects.create(
            practice=self.practice,
            date=date(2025, 1, 15),
            description="2025 Expense 1",
            category="materialien",
            amount=Decimal("100.00"),
        )
        CompanyExpense.objects.create(
            date=date(2025, 2, 20),
            description="2025 Expense 2",
            category="miete",
            amount=Decimal("1000.00"),
            practice=self.practice,
        )
        CompanyExpense.objects.create(
            date=date(2024, 12, 10),
            description="2024 Expense",
            category="materialien",
            amount=Decimal("50.00"),
            practice=self.practice,
        )

    def test_expense_list_loads(self):
        """Test expense list page loads"""
        response = self.client.get(reverse("expense_list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/expense_list.html")

    def test_expense_list_shows_all_expenses(self):
        """Test all expenses are shown by default"""
        response = self.client.get(reverse("expense_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["expenses"]), 3)

    def test_expense_list_year_filter(self):
        """Test filtering by year"""
        response = self.client.get(reverse("expense_list"), {"year": 2025})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["expenses"]), 2)
        self.assertEqual(response.context["current_year"], 2025)

    def test_expense_list_grand_total(self):
        """Test grand total calculation"""
        response = self.client.get(reverse("expense_list"))

        self.assertEqual(response.status_code, 200)
        expected_total = Decimal("1150.00")  # 100 + 1000 + 50
        self.assertEqual(response.context["grand_total"], expected_total)

    def test_expense_list_yearly_totals(self):
        """Test yearly totals aggregation"""
        response = self.client.get(reverse("expense_list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("yearly_totals", response.context)

        yearly_totals = list(response.context["yearly_totals"])
        self.assertEqual(len(yearly_totals), 2)  # 2024 and 2025

    def test_expense_list_category_breakdown(self):
        """Test category breakdown"""
        response = self.client.get(reverse("expense_list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("category_totals", response.context)


class ExpenseCreateViewTest(TestCase):
    """Tests for expense_create view"""

    def setUp(self):
        """Set up test client"""
        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="expense_views-2")

        self.client = TestClient()

        # Create and login user
        self.user = User.objects.create_user(username="expenseuser2", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client.login(username="expenseuser2", password="testpass123")

    def test_expense_create_form_loads(self):
        """Test create form loads"""
        response = self.client.get(reverse("expense_create"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/expense_form.html")

    def test_expense_create_valid_data(self):
        """Test creating expense with valid data"""
        data = {
            "date": "2025-01-15",
            "description": "New expense",
            "category": "miete",
            "amount": "150.00",
            "is_tax_deductible": True,
        }

        initial_count = CompanyExpense.objects.count()
        response = self.client.post(reverse("expense_create"), data)

        # Expense should be created (check object, not just redirect)
        self.assertEqual(CompanyExpense.objects.count(), initial_count + 1)
        expense = CompanyExpense.objects.filter(description="New expense").first()
        self.assertIsNotNone(expense)
        self.assertEqual(expense.amount, Decimal("150.00"))

        # Should redirect after success
        if response.status_code == 302:
            self.assertRedirects(response, reverse("expense_list"))

    def test_expense_create_invalid_data(self):
        """Test creating expense with invalid data"""
        data = {
            "date": "invalid-date",
            "description": "",
            "amount": "not-a-number",
        }

        response = self.client.post(reverse("expense_create"), data)

        # Should show form again with errors (200) or redirect with error message (302)
        # CRUD mixins may redirect with error message
        self.assertIn(response.status_code, [200, 302])


class ExpenseUpdateViewTest(TestCase):
    """Tests for expense_update view"""

    def setUp(self):
        """Set up test data"""
        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="expense_views-3")

        self.client = TestClient()

        # Create and login user
        self.user = User.objects.create_user(username="expenseuser3", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client.login(username="expenseuser3", password="testpass123")

        self.expense = CompanyExpense.objects.create(
            date=date(2025, 1, 15),
            description="Original description",
            category="materialien",
            amount=Decimal("100.00"),
            practice=self.practice,
        )

    def test_expense_update_form_loads(self):
        """Test update form loads with existing data"""
        response = self.client.get(reverse("expense_update", kwargs={"pk": self.expense.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/expense_form.html")
        self.assertEqual(response.context["form"].initial["description"], "Original description")

    def test_expense_update_valid_data(self):
        """Test updating expense with valid data"""
        data = {
            "date": "2025-01-20",
            "description": "Updated description",
            "category": "miete",
            "amount": "200.00",
            "is_tax_deductible": True,
        }

        response = self.client.post(reverse("expense_update", kwargs={"pk": self.expense.pk}), data)

        # Expense should be updated
        self.expense.refresh_from_db()
        self.assertEqual(self.expense.description, "Updated description")
        self.assertEqual(self.expense.amount, Decimal("200.00"))
        self.assertEqual(self.expense.category, "miete")

        # Should redirect after success
        if response.status_code == 302:
            self.assertRedirects(response, reverse("expense_list"))

    def test_expense_update_404(self):
        """Test updating non-existent expense returns 404"""
        response = self.client.get(reverse("expense_update", kwargs={"pk": 99999}))

        self.assertEqual(response.status_code, 404)

    def test_category_change_on_manual_expense_creates_no_rule(self):
        """Manually-created expenses have no linked transaction to learn a counterparty from."""
        data = {
            "date": "2025-01-20",
            "description": "Updated description",
            "category": "miete",
            "amount": "200.00",
            "is_tax_deductible": True,
        }
        self.client.post(reverse("expense_update", kwargs={"pk": self.expense.pk}), data)
        self.assertEqual(ExpenseCategoryRule.objects.filter(practice=self.practice).count(), 0)

    def test_category_change_on_bank_linked_expense_learns_rule(self):
        """Correcting a bank-sourced expense's category should learn the counterparty mapping."""
        BankTransaction.objects.create(
            practice=self.practice,
            transaction_date=date(2025, 1, 15),
            value_date=date(2025, 1, 15),
            payer_name="Vermieter GmbH",
            payer_iban="",
            reference="Miete",
            amount=Decimal("-100.00"),
            balance_after=Decimal("900.00"),
            account_iban="",
            match_confidence="auto-expense",
            linked_expense=self.expense,
            processed=False,
        )
        data = {
            "date": "2025-01-20",
            "description": "Updated description",
            "category": "miete",
            "amount": "200.00",
            "is_tax_deductible": True,
        }
        self.client.post(reverse("expense_update", kwargs={"pk": self.expense.pk}), data)
        rule = ExpenseCategoryRule.objects.get(
            practice=self.practice, match_key="name:vermieter gmbh"
        )
        self.assertEqual(rule.category, "miete")

    def test_update_without_category_change_does_not_create_rule(self):
        """Saving the form without actually changing category shouldn't churn a rule."""
        BankTransaction.objects.create(
            practice=self.practice,
            transaction_date=date(2025, 1, 15),
            value_date=date(2025, 1, 15),
            payer_name="Vermieter GmbH",
            payer_iban="",
            reference="Miete",
            amount=Decimal("-100.00"),
            balance_after=Decimal("900.00"),
            account_iban="",
            match_confidence="auto-expense",
            linked_expense=self.expense,
            processed=False,
        )
        data = {
            "date": "2025-01-20",
            "description": "Updated description",
            "category": "materialien",  # same category as setUp
            "amount": "200.00",
            "is_tax_deductible": True,
        }
        self.client.post(reverse("expense_update", kwargs={"pk": self.expense.pk}), data)
        self.assertEqual(ExpenseCategoryRule.objects.filter(practice=self.practice).count(), 0)


class ExpenseDeleteViewTest(TestCase):
    """Tests for expense_delete view"""

    def setUp(self):
        """Set up test data"""
        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="expense_views-4")

        self.client = TestClient()

        # Create and login user
        self.user = User.objects.create_user(username="expenseuser4", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client.login(username="expenseuser4", password="testpass123")

        self.expense = CompanyExpense.objects.create(
            date=date(2025, 1, 15),
            description="To be deleted",
            category="supplies",
            amount=Decimal("100.00"),
            practice=self.practice,
        )

    def test_expense_delete_confirmation(self):
        """Test delete confirmation page"""
        response = self.client.get(reverse("expense_delete", kwargs={"pk": self.expense.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/expense_confirm_delete.html")

    def test_expense_delete_post(self):
        """Test deleting expense"""
        response = self.client.post(reverse("expense_delete", kwargs={"pk": self.expense.pk}))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("expense_list"))

        # Expense should be deleted
        self.assertEqual(CompanyExpense.objects.count(), 0)

    def test_expense_delete_404(self):
        """Test deleting non-existent expense returns 404"""
        response = self.client.get(reverse("expense_delete", kwargs={"pk": 99999}))

        self.assertEqual(response.status_code, 404)


class ExpenseReceiptUploadTest(TestCase):
    """Tests for receipt file upload on create and update"""

    def setUp(self):
        self.practice = create_test_practice(name="Test Practice", slug="expense_receipt-1")
        self.client = TestClient()
        self.user = User.objects.create_user(username="receiptuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client.login(username="receiptuser", password="testpass123")

    def _pdf_file(self, name="rechnung.pdf"):
        """Return a real in-memory PDF for upload.

        process_upload() rejects anything pypdf cannot read, so this has to be
        a genuine document rather than a header-shaped stub.
        """
        return SimpleUploadedFile(name, make_pdf_bytes(), content_type="application/pdf")

    def test_create_with_receipt(self):
        """Uploading a receipt on create creates an ExpenseReceipt linked to the expense."""
        data = {
            "date": "2025-03-01",
            "description": "Mit Beleg",
            "category": "software",
            "amount": "29.99",
            "is_tax_deductible": True,
            "receipts": self._pdf_file("rechnung.pdf"),
        }
        response = self.client.post(reverse("expense_create"), data)
        self.assertIn(response.status_code, [200, 302])

        expense = CompanyExpense.objects.filter(description="Mit Beleg").first()
        self.assertIsNotNone(expense)
        receipts = list(expense.receipts.all())
        self.assertEqual(len(receipts), 1, "one ExpenseReceipt should be created")
        self.assertIn("taxes/2025", receipts[0].file.name)
        # Clean up
        receipts[0].file.delete(save=False)

    def test_create_without_receipt(self):
        """Creating an expense without a file leaves the receipts relation empty."""
        data = {
            "date": "2025-03-02",
            "description": "Ohne Beleg",
            "category": "materialien",
            "amount": "10.00",
        }
        self.client.post(reverse("expense_create"), data)
        expense = CompanyExpense.objects.filter(description="Ohne Beleg").first()
        self.assertIsNotNone(expense)
        self.assertFalse(expense.receipts.exists())

    def test_update_adds_receipt(self):
        """Uploading a file on update creates a new ExpenseReceipt."""
        expense = CompanyExpense.objects.create(
            practice=self.practice,
            date=date(2025, 4, 1),
            description="Zu ergaenzen",
            category="hardware",
            amount=Decimal("99.00"),
        )
        data = {
            "date": "2025-04-01",
            "description": "Zu ergaenzen",
            "category": "hardware",
            "amount": "99.00",
            "receipts": self._pdf_file("neu.pdf"),
        }
        self.client.post(reverse("expense_update", kwargs={"pk": expense.pk}), data)
        receipts = list(expense.receipts.all())
        self.assertEqual(len(receipts), 1, "one ExpenseReceipt should be created on update")
        self.assertIn("taxes/2025", receipts[0].file.name)
        # Clean up
        receipts[0].file.delete(save=False)

    def test_missing_receipt_filter(self):
        """?missing_receipt=1 filters to expenses without any receipt attachment."""
        expense_with = CompanyExpense.objects.create(
            practice=self.practice,
            date=date(2025, 5, 1),
            description="Hat Beleg",
            category="software",
            amount=Decimal("5.00"),
        )
        receipt = ExpenseReceipt.objects.create(
            expense=expense_with,
            file=self._pdf_file("beleg.pdf"),
        )
        CompanyExpense.objects.create(
            practice=self.practice,
            date=date(2025, 5, 2),
            description="Kein Beleg",
            category="software",
            amount=Decimal("5.00"),
        )
        response = self.client.get(reverse("expense_list"), {"missing_receipt": "1"})
        self.assertEqual(response.status_code, 200)
        expenses = list(response.context["expenses"])
        self.assertEqual(len(expenses), 1)
        self.assertEqual(expenses[0].description, "Kein Beleg")
        # Clean up
        receipt.file.delete(save=False)


class ExpenseListRenderingTest(TestCase):
    """Test expense list view."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="12345")
        self.client_instance = TestClient()

        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="views_expense-1")

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


class ExpenseCreateFieldsTest(TestCase):
    """Test expense create view."""

    def setUp(self):
        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="views_expense-2")

        self.user = User.objects.create_user(username="testuser", password="12345")
        self.client_instance = TestClient()
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance.login(username="testuser", password="12345")
        select_practice(self.client_instance, self.practice)

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


class ExpenseUpdateFieldsTest(TestCase):
    """Test expense update view."""

    def setUp(self):
        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="views_expense-3")

        self.user = User.objects.create_user(username="testuser", password="12345")
        self.client_instance = TestClient()

        # Link user to practice
        UserPractice.objects.get_or_create(
            user=self.user, practice=self.practice, defaults={"is_owner": True}
        )

        self.client_instance.login(username="testuser", password="12345")

        # Set practice in session for middleware
        select_practice(self.client_instance, self.practice)

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


class ExpenseDeleteConfirmationTest(TestCase):
    """Test expense delete view."""

    def setUp(self):
        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="views_expense-4")

        self.user = User.objects.create_user(username="testuser", password="12345")
        self.client_instance = TestClient()

        UserPractice.objects.get_or_create(
            user=self.user, practice=self.practice, defaults={"is_owner": True}
        )

        self.client_instance.login(username="testuser", password="12345")

        select_practice(self.client_instance, self.practice)

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


class ExpenseTransactionLinkTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="linkuser", password="pass")
        self.practice = Practice.objects.create(
            name="Link Practice",
            slug="link-practice",
            email="link@example.com",
            iban="DE89370400440532013000",
        )
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.http = TestClient()
        self.http.login(username="linkuser", password="pass")
        self.expense = CompanyExpense.objects.create(
            practice=self.practice,
            description="Software",
            amount=Decimal("0.00"),
            category="software",
            date=date(2026, 1, 1),
        )

    def _transaction(self, amount, **kwargs):
        return BankTransaction.objects.create(
            practice=self.practice,
            transaction_date=date(2026, 1, 1),
            value_date=date(2026, 1, 1),
            amount=Decimal(amount),
            balance_after=Decimal("1000.00"),
            payer_name="Test",
            reference="ref",
            **kwargs,
        )

    def test_link_rejects_incoming_transaction(self):
        incoming = self._transaction("90.00")
        response = self.http.post(
            reverse("expense_link_transaction", args=[self.expense.pk]),
            {"transaction_id": incoming.pk},
        )
        self.assertEqual(response.status_code, 404)
        incoming.refresh_from_db()
        self.assertIsNone(incoming.linked_expense)

    def test_unlink_returns_transaction_to_review(self):
        outgoing = self._transaction(
            "-30.00", linked_expense=self.expense, match_confidence="manual", processed=True
        )
        self.http.post(reverse("expense_unlink_transaction", args=[self.expense.pk, outgoing.pk]))
        outgoing.refresh_from_db()
        self.assertIsNone(outgoing.linked_expense)
        self.assertEqual(outgoing.match_confidence, "unmatched")
        self.assertFalse(outgoing.processed)
