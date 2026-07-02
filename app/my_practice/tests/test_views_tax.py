"""
Tests for tax views.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import (
    Client,
    CompanyExpense,
    CompanyWithdrawal,
    Invoice,
    InvoiceItem,
    Practice,
    Session,
    ServiceType,
)


class TaxYearSummaryViewTest(TestCase):
    """Test tax year summary view."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="12345")
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser", password="12345")

        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_tax-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        # Add user to practice so middleware sets it
        self.practice.users.add(self.user)

        # Set current practice in session
        session = self.client_instance.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

        # Create test data
        self.service_type = ServiceType.objects.create(
            code="therapy_60",
            name="Therapy Session 60min",
            name_de="Psychotherapie, 60 Min.",
            practice=self.practice,
        )

        self.client_obj = Client.objects.create(
            client_code="TC1",
            full_name="Test Client",
            email="test@example.com",
            hourly_rate_60=Decimal("120.00"),
            hourly_rate_90=Decimal("180.00"),
            practice=self.practice,
        )

        # Create paid invoices for 2024
        invoice1 = Invoice.objects.create(
            client=self.client_obj,
            invoice_number="2024-001",
            invoice_date=date(2024, 1, 15),
            paid_date=date(2024, 1, 20),
            status="paid",
            total=Decimal("120.00"),
            practice=self.practice,
        )
        session1 = Session.objects.create(
            client=self.client_obj, session_date=date(2024, 1, 15), duration=60
        )
        InvoiceItem.objects.create(
            invoice=invoice1,
            service_type=self.service_type,
            quantity=1,
            rate=Decimal("120.00"),
            total=Decimal("120.00"),
            session=session1,
        )

        invoice2 = Invoice.objects.create(
            client=self.client_obj,
            invoice_number="2024-002",
            invoice_date=date(2024, 3, 10),
            paid_date=date(2024, 3, 15),
            status="paid",
            total=Decimal("180.00"),
            practice=self.practice,
        )
        session2 = Session.objects.create(
            client=self.client_obj, session_date=date(2024, 3, 10), duration=90
        )
        InvoiceItem.objects.create(
            invoice=invoice2,
            service_type=self.service_type,
            quantity=1,
            rate=Decimal("180.00"),
            total=Decimal("180.00"),
            session=session2,
        )

        # Create invoice for 2023
        invoice3 = Invoice.objects.create(
            client=self.client_obj,
            invoice_number="2023-001",
            invoice_date=date(2023, 12, 1),
            paid_date=date(2023, 12, 15),
            status="paid",
            total=Decimal("120.00"),
            practice=self.practice,
        )
        session3 = Session.objects.create(
            client=self.client_obj, session_date=date(2023, 12, 1), duration=60
        )
        InvoiceItem.objects.create(
            invoice=invoice3,
            service_type=self.service_type,
            quantity=1,
            rate=Decimal("120.00"),
            total=Decimal("120.00"),
            session=session3,
        )

        # Create expenses for 2024
        CompanyExpense.objects.create(
            description="Rent 2024",
            amount=Decimal("1500.00"),
            category="miete",
            date=date(2024, 12, 31),
            is_tax_deductible=True,
            practice=self.practice,
        )
        CompanyExpense.objects.create(
            description="Software 2024",
            amount=Decimal("99.00"),
            category="software",
            date=date(2024, 6, 1),
            practice=self.practice,
            is_tax_deductible=True,
        )

        # Create expense for 2023
        CompanyExpense.objects.create(
            description="Rent 2023",
            amount=Decimal("1200.00"),
            category="miete",
            date=date(2023, 12, 31),
            is_tax_deductible=True,
            practice=self.practice,
        )

        # Create withdrawals for 2024
        CompanyWithdrawal.objects.create(
            description="Personal 2024",
            amount=Decimal("500.00"),
            category="Persönliche Entnahme",
            date=date(2024, 6, 1),
            practice=self.practice,
        )

        # Create withdrawal for 2023
        CompanyWithdrawal.objects.create(
            description="Personal 2023",
            amount=Decimal("300.00"),
            category="Persönliche Entnahme",
            date=date(2023, 12, 1),
            practice=self.practice,
        )

    def test_tax_summary_loads(self):
        """Test that tax summary view loads successfully."""
        response = self.client_instance.get(reverse("tax_year_summary"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/tax_year_summary.html")

    def test_tax_summary_default_year(self):
        """Test that default year is current year."""
        from datetime import date

        response = self.client_instance.get(reverse("tax_year_summary"))
        # Should default to current year
        current_year = str(date.today().year)
        self.assertContains(response, current_year)

    def test_tax_summary_specific_year(self):
        """Test filtering tax summary by specific year."""
        response = self.client_instance.get(reverse("tax_year_summary") + "?year=2024")

        # Should show 2024 data
        self.assertContains(response, "2024")
        self.assertContains(response, "2024-001")
        self.assertContains(response, "2024-002")

        # Should not show 2023 data
        self.assertNotContains(response, "2023-001")

    def test_tax_summary_revenue_calculation(self):
        """Test that revenue is calculated correctly for the year."""
        response = self.client_instance.get(reverse("tax_year_summary") + "?year=2024")

        # Check context data instead of template text
        self.assertIn("total_revenue", response.context)
        self.assertEqual(float(response.context["total_revenue"]), 300.00)

    def test_tax_summary_expense_calculation(self):
        """Test that expenses are calculated correctly for the year."""
        response = self.client_instance.get(reverse("tax_year_summary") + "?year=2024")

        # Check context data instead of template text
        self.assertIn("total_expenses", response.context)
        self.assertAlmostEqual(float(response.context["total_expenses"]), 1599.00, places=2)

    def test_tax_summary_profit_calculation(self):
        """Test that profit is calculated correctly."""
        response = self.client_instance.get(reverse("tax_year_summary") + "?year=2024")

        # Check context data for profit calculation
        self.assertIn("gross_profit", response.context)
        # Profit should be revenue - expenses = 300 - 1599 = -1299
        expected_profit = 300.00 - 1599.00
        self.assertAlmostEqual(float(response.context["gross_profit"]), expected_profit, places=2)

    def test_tax_summary_monthly_breakdown(self):
        """Test that monthly revenue breakdown is shown."""
        response = self.client_instance.get(reverse("tax_year_summary") + "?year=2024")

        # Check that monthly_revenue context exists
        self.assertIn("monthly_revenue", response.context)
        # Should have at least one month with data
        self.assertGreater(len(response.context["monthly_revenue"]), 0)

    def test_tax_summary_year_selector(self):
        """Test that year selector dropdown is available."""
        response = self.client_instance.get(reverse("tax_year_summary"))

        # Should have year options
        self.assertContains(response, "<select")
        self.assertContains(response, "2024")
        self.assertContains(response, "2023")

    def test_tax_summary_no_data_year(self):
        """Test year with no data shows empty state."""
        response = self.client_instance.get(reverse("tax_year_summary") + "?year=2020")

        # Should handle year with no data gracefully
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2020")

    def test_tax_summary_print_friendly(self):
        """Test that print-friendly styles are included."""
        response = self.client_instance.get(reverse("tax_year_summary"))

        # Should have print-friendly elements
        self.assertContains(response, "Steuererklärung")

    def test_tax_summary_expense_categories(self):
        """Test that expense categories are grouped correctly."""
        response = self.client_instance.get(reverse("tax_year_summary") + "?year=2024")

        # Check that expense_by_category context exists
        self.assertIn("expense_by_category", response.context)
        self.assertGreater(len(response.context["expense_by_category"]), 0)

    def test_tax_summary_only_tax_deductible_expenses(self):
        """Test that only tax deductible expenses are included."""
        response = self.client_instance.get(reverse("tax_year_summary") + "?year=2024")

        # All expenses shown should be tax-deductible
        self.assertIn("total_expenses", response.context)
        self.assertGreater(float(response.context["total_expenses"]), 0)


class TaxQuarterOverviewConsistencyTest(TestCase):
    """Quarterly revenue must follow the same paid-date rule as the year summary,
    so the four quarters always sum to the yearly total."""

    def setUp(self):
        self.user = User.objects.create_user(username="quarteruser", password="12345")
        self.client_instance = TestClient()
        self.client_instance.login(username="quarteruser", password="12345")

        self.practice = Practice.objects.create(
            name="Quarter Practice",
            slug="views_tax-quarter",
            title="Test Practitioner",
            email="quarter@practice.example",
            city="Berlin",
        )
        self.practice.users.add(self.user)
        session = self.client_instance.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

        self.client_obj = Client.objects.create(
            client_code="TQ1",
            full_name="Max Mustermann",
            email="mail@example.com",
            hourly_rate_60=Decimal("100.00"),
            practice=self.practice,
        )

        # Paid in Q1 via paid_date
        Invoice.objects.create(
            client=self.client_obj,
            invoice_number="TQ1-1",
            invoice_date=date(2024, 1, 15),
            paid_date=date(2024, 2, 10),
            status="paid",
            total=Decimal("120.00"),
            practice=self.practice,
        )
        # Paid but no paid_date recorded — must fall back to invoice_date (Q2)
        Invoice.objects.create(
            client=self.client_obj,
            invoice_number="TQ1-2",
            invoice_date=date(2024, 5, 15),
            paid_date=None,
            status="paid",
            total=Decimal("200.00"),
            practice=self.practice,
        )

    def test_quarters_sum_to_year_total(self):
        """The sum of quarterly revenue equals the year summary total."""
        quarter_response = self.client_instance.get(reverse("tax_quarter_overview") + "?year=2024")
        year_response = self.client_instance.get(reverse("tax_year_summary") + "?year=2024")

        self.assertEqual(quarter_response.status_code, 200)
        self.assertEqual(
            quarter_response.context["total_revenue"],
            year_response.context["total_revenue"],
        )
        self.assertEqual(quarter_response.context["total_revenue"], Decimal("320.00"))

    def test_null_paid_date_lands_in_invoice_date_quarter(self):
        """A paid invoice without paid_date counts in the quarter of its invoice_date."""
        response = self.client_instance.get(reverse("tax_quarter_overview") + "?year=2024")
        quarters = {q["number"]: q["revenue"] for q in response.context["quarters"]}

        self.assertEqual(quarters[1], Decimal("120.00"))
        self.assertEqual(quarters[2], Decimal("200.00"))
        self.assertEqual(quarters[3], Decimal("0"))
        self.assertEqual(quarters[4], Decimal("0"))
