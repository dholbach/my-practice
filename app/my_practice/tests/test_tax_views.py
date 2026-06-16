"""
Tests for tax year summary view.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse
from my_practice.models import (
    Client,
    CompanyExpense,
    CompanyWithdrawal,
    Invoice,
    Practice,
)


class TaxYearSummaryViewTest(TestCase):
    """Tests for tax_year_summary view"""

    def setUp(self):
        """Set up test data"""
        # Create user and authenticate
        self.user = User.objects.create_user(username="testuser", password="12345")
        self.client_http = TestClient()
        self.client_http.login(username="testuser", password="12345")

        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="tax-views-fix",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        # Add user to practice and set in session
        self.practice.users.add(self.user)
        session = self.client_http.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

        # Create test client
        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            practice=self.practice,
        )

        # Create invoices for 2025
        self.invoice_2025_paid = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date(2025, 1, 15),
            paid_date=date(2025, 1, 20),
            status="paid",
            total=Decimal("1000.00"),
            practice=self.practice,
        )

        self.invoice_2025_draft = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-2",
            invoice_date=date(2025, 2, 15),
            status="draft",
            total=Decimal("500.00"),
            practice=self.practice,
        )

        # Create expenses for 2025
        self.expense_2025 = CompanyExpense.objects.create(
            date=date(2025, 1, 10),
            description="Test expense",
            category="supplies",
            amount=Decimal("200.00"),
            is_tax_deductible=True,
            practice=self.practice,
        )

        # Create withdrawals for 2025
        self.withdrawal_2025 = CompanyWithdrawal.objects.create(
            date=date(2025, 1, 25),
            amount=Decimal("500.00"),
            category="salary",
            practice=self.practice,
        )

    def test_tax_summary_loads(self):
        """Test tax summary page loads successfully"""
        response = self.client_http.get(reverse("tax_year_summary"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/tax_year_summary.html")

    def test_tax_summary_default_year(self):
        """Test tax summary defaults to current year"""
        response = self.client_http.get(reverse("tax_year_summary"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["year"], date.today().year)

    def test_tax_summary_specific_year(self):
        """Test tax summary for specific year"""
        response = self.client_http.get(reverse("tax_year_summary"), {"year": 2025})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["year"], 2025)

    def test_tax_summary_revenue_only_paid(self):
        """Test only paid invoices are included in revenue"""
        response = self.client_http.get(reverse("tax_year_summary"), {"year": 2025})

        self.assertEqual(response.status_code, 200)

        # Only paid invoice should be counted
        self.assertEqual(response.context["total_revenue"], Decimal("1000.00"))
        self.assertEqual(response.context["invoice_count"], 1)

    def test_tax_summary_expenses(self):
        """Test only tax-deductible expenses are included"""
        response = self.client_http.get(reverse("tax_year_summary"), {"year": 2025})

        self.assertEqual(response.status_code, 200)
        # Only tax-deductible expenses are shown
        self.assertEqual(response.context["total_expenses"], Decimal("200.00"))
        self.assertEqual(response.context["expense_count"], 1)

    def test_tax_summary_profit_calculation(self):
        """Test profit calculations are correct"""
        response = self.client_http.get(reverse("tax_year_summary"), {"year": 2025})

        self.assertEqual(response.status_code, 200)

        # Gross profit = revenue - tax-deductible expenses
        expected_gross = Decimal("1000.00") - Decimal("200.00")
        self.assertEqual(response.context["gross_profit"], expected_gross)

    def test_tax_summary_empty_year(self):
        """Test tax summary for year with no data"""
        response = self.client_http.get(reverse("tax_year_summary"), {"year": 2020})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_revenue"], Decimal("0"))
        self.assertEqual(response.context["total_expenses"], Decimal("0"))

    def test_tax_summary_category_breakdowns(self):
        """Test category breakdowns are included"""
        response = self.client_http.get(reverse("tax_year_summary"), {"year": 2025})

        self.assertEqual(response.status_code, 200)
        self.assertIn("expense_by_category", response.context)

    def test_tax_summary_monthly_revenue(self):
        """Test monthly revenue breakdown is included"""
        response = self.client_http.get(reverse("tax_year_summary"), {"year": 2025})

        self.assertEqual(response.status_code, 200)
        self.assertIn("monthly_revenue", response.context)

        # Check monthly data exists
        monthly_data = response.context["monthly_revenue"]
        self.assertGreater(len(monthly_data), 0)
        # Verify structure
        if monthly_data:
            first_month = monthly_data[0]
            self.assertIn("month", first_month)
            self.assertIn("amount", first_month)
            self.assertIn("count", first_month)

    def test_tax_summary_home_office_deduction(self):
        """Home-office deduction is calculated from non-practice weekdays."""
        self.practice.practice_weekdays = [0, 2, 4]
        self.practice.save(update_fields=["practice_weekdays"])

        response = self.client_http.get(reverse("tax_year_summary"), {"year": 2025})

        self.assertEqual(response.status_code, 200)
        self.assertIn("home_office", response.context)
        self.assertIn("home_office_deduction", response.context)
        self.assertGreater(response.context["home_office_deduction"], Decimal("0"))

        expected_profit = (
            Decimal("1000.00") - Decimal("200.00") - response.context["home_office_deduction"]
        )
        self.assertEqual(response.context["gross_profit"], expected_profit)

    def test_tax_summary_shows_multi_practice_allocation_notice(self):
        """Allocation notice appears when user has more than one active practice."""
        second_practice = Practice.objects.create(
            name="Coaching Practice",
            slug="tax-views-fix-coaching",
            title="Coach",
            email="coach@example.com",
            city="Berlin",
        )
        second_practice.users.add(self.user)

        response = self.client_http.get(reverse("tax_year_summary"), {"year": 2025})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["show_multi_practice_allocation_notice"])
        self.assertContains(response, "Pauschalen-Aufteilung bei mehreren Tätigkeiten")

    def test_practice_split_computes_ratios(self):
        """practice_split contains revenue and session-share ratios when multi-practice."""
        second_practice = Practice.objects.create(
            name="Coaching Practice",
            slug="tax-views-fix-coaching2",
            title="Coach",
            email="coach2@example.com",
            city="Berlin",
        )
        second_practice.users.add(self.user)

        response = self.client_http.get(reverse("tax_year_summary"), {"year": 2025})

        self.assertEqual(response.status_code, 200)
        split = response.context["practice_split"]
        self.assertIsNotNone(split)
        # This practice has 1000€ revenue; second has 0€ → share should be 1
        self.assertEqual(split.revenue_share, Decimal("1"))
        # No sessions in DB → falls back to 1
        self.assertEqual(split.session_share, Decimal("1"))
        # Pre-computed split amounts are present
        self.assertIn("home_office_split_revenue", response.context)
        self.assertIn("fahrtkosten_split_revenue", response.context)

    def test_practice_split_is_none_for_single_practice(self):
        """practice_split is None when only one active practice."""
        response = self.client_http.get(reverse("tax_year_summary"), {"year": 2025})

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["practice_split"])


class TaxYearNoteViewTest(TestCase):
    """Tests for save_tax_year_note view and TaxYearNote model integration."""

    def setUp(self):
        self.user = User.objects.create_user(username="noteuser", password="12345")
        self.client_http = TestClient()
        self.client_http.login(username="noteuser", password="12345")

        self.practice = Practice.objects.create(
            name="Note Test Practice",
            slug="note-test-practice",
            title="Dr. Muster",
            email="note@example.com",
            city="Berlin",
        )
        self.practice.users.add(self.user)
        session = self.client_http.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

    def test_save_note_creates_record(self):
        """POST to save_tax_year_note creates a TaxYearNote record."""
        from my_practice.models import TaxYearNote

        response = self.client_http.post(
            reverse("save_tax_year_note"),
            {"year": "2025", "note": "Einnahmenanteil 95/5"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["saved"])
        self.assertTrue(TaxYearNote.objects.filter(practice=self.practice, year=2025).exists())

    def test_save_note_updates_existing(self):
        """Second POST with same year overwrites the note."""
        from my_practice.models import TaxYearNote

        self.client_http.post(reverse("save_tax_year_note"), {"year": "2025", "note": "First note"})
        self.client_http.post(
            reverse("save_tax_year_note"), {"year": "2025", "note": "Updated note"}
        )
        note = TaxYearNote.objects.get(practice=self.practice, year=2025)
        self.assertEqual(note.allocation_note, "Updated note")

    def test_save_note_rejects_invalid_year(self):
        """POST with an out-of-range year returns 400."""
        response = self.client_http.post(
            reverse("save_tax_year_note"), {"year": "1800", "note": "Bad year"}
        )
        self.assertEqual(response.status_code, 400)

    def test_tax_year_note_in_summary_context(self):
        """tax_year_note context variable is populated after saving a note."""
        from my_practice.models import TaxYearNote

        TaxYearNote.objects.create(practice=self.practice, year=2025, allocation_note="My note")
        response = self.client_http.get(reverse("tax_year_summary"), {"year": 2025})
        self.assertEqual(response.status_code, 200)
        note = response.context["tax_year_note"]
        self.assertIsNotNone(note)
        self.assertEqual(note.allocation_note, "My note")

    def test_tax_year_note_none_when_absent(self):
        """tax_year_note is None when no note has been saved yet."""
        response = self.client_http.get(reverse("tax_year_summary"), {"year": 2024})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["tax_year_note"])


class WorkdayAuditViewTest(TestCase):
    """Tests for tax_workday_audit view."""

    def setUp(self):
        self.user = User.objects.create_user(username="audituser", password="12345")
        self.client_http = TestClient()
        self.client_http.login(username="audituser", password="12345")

        self.practice = Practice.objects.create(
            name="Audit Test Practice",
            slug="audit-test-practice",
            title="Dr. Audit",
            email="audit@example.com",
            city="Berlin",
            practice_weekdays=[0, 2, 4],  # Mon, Wed, Fri in-practice
        )
        self.practice.users.add(self.user)
        session = self.client_http.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

    def test_audit_page_loads(self):
        """GET tax_workday_audit returns 200."""
        response = self.client_http.get(reverse("tax_workday_audit"), {"year": 2025})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/tax_workday_audit.html")

    def test_audit_context_has_entries(self):
        """Audit result contains entries for a full year."""
        response = self.client_http.get(reverse("tax_workday_audit"), {"year": 2025})
        self.assertEqual(response.status_code, 200)
        audit = response.context["audit"]
        self.assertIsNotNone(audit)
        self.assertGreater(len(audit.entries), 0)

    def test_audit_practice_vs_home_office_split(self):
        """Practice weekdays produce practice-day entries; others are home-office."""
        response = self.client_http.get(reverse("tax_workday_audit"), {"year": 2025})
        audit = response.context["audit"]
        # With Mon/Wed/Fri as practice days, both practice_days and home_office_days > 0
        self.assertGreater(audit.practice_days, 0)
        self.assertGreater(audit.home_office_days, 0)
