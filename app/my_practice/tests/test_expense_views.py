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
from my_practice.models import CompanyExpense, ExpenseReceipt, Practice, UserPractice

User = get_user_model()


class ExpenseListViewTest(TestCase):
    """Tests for expense_list view"""

    def setUp(self):
        """Set up test data"""
        self.client = TestClient()

        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="expense_views-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

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
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="expense_views-2",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

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
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="expense_views-3",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

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


class ExpenseDeleteViewTest(TestCase):
    """Tests for expense_delete view"""

    def setUp(self):
        """Set up test data"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="expense_views-4",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

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
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="expense_receipt-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.client = TestClient()
        self.user = User.objects.create_user(username="receiptuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client.login(username="receiptuser", password="testpass123")

    def _pdf_file(self, name="rechnung.pdf"):
        """Return a minimal in-memory PDF for upload."""
        content = b"%PDF-1.0\n1 0 obj<</Type /Catalog>>endobj\n"
        return SimpleUploadedFile(name, content, content_type="application/pdf")

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
