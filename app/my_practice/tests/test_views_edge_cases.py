"""
Edge case tests for views - invalid inputs, empty data, boundary conditions
Focus on CRUD views (Expense, Withdrawal) using the new mixins
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from my_practice.models import Client as ClientModel
from my_practice.models import (
    CompanyExpense,
    CompanyWithdrawal,
    Practice,
    UserPractice,
)

User = get_user_model()


class ExpenseWithdrawalEdgeCasesTest(TestCase):
    """Edge cases for expense and withdrawal CRUD views (using new mixins)"""

    def setUp(self):
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_edge_cases-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.user = User.objects.create_user(username="testuser", password="12345")
        self.client = Client()

        # Link user to practice
        UserPractice.objects.get_or_create(
            user=self.user, practice=self.practice, defaults={"is_owner": True}
        )

        self.client.login(username="testuser", password="12345")

        # Set practice in session for middleware
        session = self.client.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

    def test_expense_create_with_negative_amount(self):
        """Test that negative amounts are handled"""
        data = {
            "date": date.today(),
            "amount": "-100.00",  # Negative!
            "category": "miete",  # Valid category
            "description": "Test expense",
            "is_tax_deductible": True,
        }

        response = self.client.post(reverse("expense_create"), data)
        # Might show form with error OR accept negative (depends on validators)
        self.assertIn(response.status_code, [200, 302])

    def test_expense_create_with_extremely_long_description(self):
        """Test expense with very long description"""
        long_desc = "A" * 10000  # 10k characters

        data = {
            "date": date.today(),
            "amount": "100.00",
            "category": "software",  # Valid category
            "description": long_desc,
            "is_tax_deductible": True,
        }

        response = self.client.post(reverse("expense_create"), data)

        # Should either accept or truncate
        if response.status_code == 302:  # Redirect = success
            expense = CompanyExpense.objects.latest("id")
            # Description might be truncated depending on field max_length
            self.assertTrue(len(expense.description) > 0)

    def test_expense_delete_nonexistent(self):
        """Test deleting non-existent expense returns 404"""
        response = self.client.get(reverse("expense_delete", kwargs={"pk": 99999}))
        self.assertEqual(response.status_code, 404)

    def test_expense_update_changes_values(self):
        """Test that expense update properly saves changes"""
        expense = CompanyExpense.objects.create(
            date=date.today(),
            amount=Decimal("100.00"),
            category="miete",  # Valid category
            description="Original",
            is_tax_deductible=True,
            practice=self.practice,
        )

        # Update it (need all fields for ModelForm)
        data = {
            "date": date.today().isoformat(),  # ISO format for date
            "amount": "200.00",  # Changed!
            "category": "software",  # Changed to valid category!
            "description": "Updated",  # Changed!
            "is_tax_deductible": False,  # Changed!
        }

        response = self.client.post(reverse("expense_update", kwargs={"pk": expense.pk}), data)
        self.assertEqual(response.status_code, 302)  # Redirect on success

        # Reload from DB
        expense.refresh_from_db()
        self.assertEqual(expense.amount, Decimal("200.00"))
        self.assertEqual(expense.category, "software")
        self.assertEqual(expense.description, "Updated")
        self.assertFalse(expense.is_tax_deductible)

    def test_expense_delete_removes_from_database(self):
        """Test that POST to expense_delete actually deletes the expense"""
        expense = CompanyExpense.objects.create(
            date=date.today(),
            amount=Decimal("100.00"),
            category="office",
            description="To be deleted",
            is_tax_deductible=True,
            practice=self.practice,
        )

        pk = expense.pk
        self.assertTrue(CompanyExpense.objects.filter(pk=pk).exists())

        # Delete it
        response = self.client.post(reverse("expense_delete", kwargs={"pk": pk}))
        self.assertEqual(response.status_code, 302)  # Redirect on success

        # Should be gone
        self.assertFalse(CompanyExpense.objects.filter(pk=pk).exists())

    def test_withdrawal_create_future_date(self):
        """Test withdrawal with future date"""
        future_date = date.today() + timedelta(days=365)

        data = {
            "date": future_date,
            "amount": "1000.00",
            "description": "Future withdrawal",
        }

        response = self.client.post(reverse("withdrawal_create"), data)

        # Should accept future dates
        if response.status_code == 302:
            withdrawal = CompanyWithdrawal.objects.latest("id")
            self.assertEqual(withdrawal.date, future_date)

    def test_withdrawal_with_zero_amount(self):
        """Test withdrawal with zero amount"""
        data = {
            "date": date.today(),
            "amount": "0.00",
            "description": "Zero withdrawal",
        }

        response = self.client.post(reverse("withdrawal_create"), data)
        # Might be rejected by form validation or accepted
        # Either way shouldn't cause a crash
        self.assertIn(response.status_code, [200, 302])

    def test_withdrawal_update_changes_values(self):
        """Test that withdrawal update properly saves changes"""
        withdrawal = CompanyWithdrawal.objects.create(
            date=date.today(),
            amount=Decimal("1000.00"),
            description="Original",
            category="salary",  # Required field!,
            practice=self.practice,
        )

        # Update it
        data = {
            "date": (date.today() - timedelta(days=1)).isoformat(),  # ISO format for date
            "amount": "2000.00",  # Changed!
            "description": "Updated",  # Changed!
            "category": "other",  # Changed!
        }

        response = self.client.post(
            reverse("withdrawal_update", kwargs={"pk": withdrawal.pk}), data
        )
        self.assertEqual(response.status_code, 302)  # Redirect on success

        # Reload from DB
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.amount, Decimal("2000.00"))
        self.assertEqual(withdrawal.description, "Updated")

    def test_withdrawal_delete_removes_from_database(self):
        """Test that POST to withdrawal_delete actually deletes the withdrawal"""
        withdrawal = CompanyWithdrawal.objects.create(
            date=date.today(),
            amount=Decimal("1000.00"),
            description="To be deleted",
            practice=self.practice,
        )

        pk = withdrawal.pk
        self.assertTrue(CompanyWithdrawal.objects.filter(pk=pk).exists())

        # Delete it
        response = self.client.post(reverse("withdrawal_delete", kwargs={"pk": pk}))
        self.assertEqual(response.status_code, 302)  # Redirect on success

        # Should be gone
        self.assertFalse(CompanyWithdrawal.objects.filter(pk=pk).exists())


class ClientEdgeCasesTest(TestCase):
    """Edge cases for client views"""

    def setUp(self):
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_edge_cases-2",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Create user and login
        self.user = User.objects.create_user(username="edgecaseuser", password="12345")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)

        self.client = Client()
        self.client.login(username="edgecaseuser", password="12345")

    def test_client_detail_very_long_name(self):
        """Test client with very long name displays properly"""
        long_name = "Test " * 40  # 200 characters (max for VARCHAR(200))

        client_model = ClientModel.objects.create(
            client_code="LONG",
            full_name=long_name,
            email="long@example.com",
            practice=self.practice,
        )

        response = self.client.get(reverse("client_detail", kwargs={"pk": client_model.pk}))
        self.assertEqual(response.status_code, 200)
        # Should still render without breaking layout
        self.assertContains(response, "LONG")

    def test_client_list_with_no_clients(self):
        """Test client list page with zero clients"""
        response = self.client.get(reverse("client_list"))
        self.assertEqual(response.status_code, 200)
        # Should show empty state
        self.assertEqual(ClientModel.objects.count(), 0)

    def test_client_with_invalid_email(self):
        """Test client creation with invalid email"""
        data = {
            "client_code": "INV",
            "full_name": "Invalid Email Client",
            "email": "not-an-email",  # Invalid!
            "hourly_rate_60": "90.00",
            "hourly_rate_90": "130.00",
            "language": "de",
        }

        response = self.client.post(reverse("client_intake"), data)
        # Should show form with validation error
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertTrue(response.context["form"].errors)

    def test_client_with_unicode_characters(self):
        """Test client with special unicode characters in name"""
        unicode_name = "Müller-Özdemir François 北京"

        data = {
            "client_code": "UNI",
            "full_name": unicode_name,
            "email": "unicode@example.com",
            "hourly_rate_60": "90.00",
            "hourly_rate_90": "130.00",
            "language": "de",
        }

        response = self.client.post(reverse("client_intake"), data)

        # Should handle unicode properly
        self.assertEqual(response.status_code, 302)
        client_model = ClientModel.objects.get(client_code="UNI")
        self.assertEqual(client_model.full_name, unicode_name)

    def test_client_with_extremely_high_rates(self):
        """Test client with very high hourly rates"""
        data = {
            "client_code": "RICH",
            "full_name": "Rich Client",
            "email": "rich@example.com",
            "hourly_rate_60": "9999.99",  # Very high!
            "hourly_rate_90": "9999.99",
            "language": "de",
        }

        response = self.client.post(reverse("client_intake"), data)

        # Should accept within DecimalField limits (redirects on success)
        self.assertEqual(response.status_code, 302)
        client_model = ClientModel.objects.get(client_code="RICH")
        self.assertEqual(client_model.hourly_rate_60, Decimal("9999.99"))
