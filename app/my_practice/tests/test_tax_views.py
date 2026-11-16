"""
Tests for tax year summary view.
"""

from datetime import date
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from my_practice.models import (
    Client,
    CompanyExpense,
    CompanyWithdrawal,
    Invoice,
    InvoiceItem,
    Practice,
    ServiceType,
    Session,
    allow_issued_invoice_writes,
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

    def test_save_settlement_without_note_preserves_existing_note(self):
        """POST with settlement_amount/settlement_date but no 'note' key must not clear the stored note.

        Mirrors the settlement-editing widget on tax_quarter_overview.html, which posts
        settlement_amount/settlement_date only and never includes a 'note' field.
        """
        from my_practice.models import TaxYearNote

        self.client_http.post(
            reverse("save_tax_year_note"), {"year": "2025", "note": "Einnahmenanteil 95/5"}
        )
        response = self.client_http.post(
            reverse("save_tax_year_note"),
            {"year": "2025", "settlement_amount": "123.45", "settlement_date": "2025-06-01"},
        )
        self.assertEqual(response.status_code, 200)
        note = TaxYearNote.objects.get(practice=self.practice, year=2025)
        self.assertEqual(note.allocation_note, "Einnahmenanteil 95/5")
        self.assertEqual(note.settlement_amount, Decimal("123.45"))

    def test_save_note_rejects_invalid_year(self):
        """POST with an out-of-range year returns 400."""
        response = self.client_http.post(
            reverse("save_tax_year_note"), {"year": "1800", "note": "Bad year"}
        )
        self.assertEqual(response.status_code, 400)

    def test_save_settlement_accepts_comma_decimal_amount(self):
        """A German-formatted "123,45" amount is normalized like a plain "123.45" one."""
        from my_practice.models import TaxYearNote

        response = self.client_http.post(
            reverse("save_tax_year_note"),
            {"year": "2025", "settlement_amount": "123,45", "settlement_date": "2025-06-01"},
        )
        self.assertEqual(response.status_code, 200)
        note = TaxYearNote.objects.get(practice=self.practice, year=2025)
        self.assertEqual(note.settlement_amount, Decimal("123.45"))

    def test_save_settlement_rejects_invalid_amount(self):
        """A non-numeric settlement_amount returns 400 without touching the record."""
        response = self.client_http.post(
            reverse("save_tax_year_note"),
            {"year": "2025", "settlement_amount": "not-a-number"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_save_settlement_rejects_invalid_date(self):
        """A non-ISO settlement_date returns 400 without touching the record."""
        response = self.client_http.post(
            reverse("save_tax_year_note"),
            {"year": "2025", "settlement_date": "01.06.2025"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_save_settlement_empty_amount_clears_it(self):
        """Posting settlement_amount as an empty string clears a previously saved value."""
        from my_practice.models import TaxYearNote

        self.client_http.post(
            reverse("save_tax_year_note"),
            {"year": "2025", "settlement_amount": "123.45"},
        )
        response = self.client_http.post(
            reverse("save_tax_year_note"),
            {"year": "2025", "settlement_amount": ""},
        )
        self.assertEqual(response.status_code, 200)
        note = TaxYearNote.objects.get(practice=self.practice, year=2025)
        self.assertIsNone(note.settlement_amount)

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


class TaxYearSummaryRenderingTest(TestCase):
    """Test tax year summary view."""

    @allow_issued_invoice_writes()
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

    def test_tax_summary_year_selector(self):
        """Test that year selector dropdown is available."""
        response = self.client_instance.get(reverse("tax_year_summary"))

        # Should have year options
        self.assertContains(response, "<select")
        self.assertContains(response, "2024")
        self.assertContains(response, "2023")

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


class TaxQuarterOverviewConsistencyTest(TestCase):
    """Quarterly revenue must follow the same paid-date rule as the year summary,
    so the four quarters always sum to the yearly total."""

    @allow_issued_invoice_writes()
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

    def test_add_payment_link_returns_to_the_same_year(self):
        """The quick-add link carries ?next= back to this overview, year included
        — saving a prepayment shouldn't land the user on the withdrawal list, and
        coming back to a different year is no better than not coming back."""
        response = self.client_instance.get(reverse("tax_quarter_overview") + "?year=2024")
        add_url = response.context["add_payment_url"]

        parsed = urlparse(add_url)
        params = parse_qs(parsed.query)
        self.assertEqual(parsed.path, reverse("withdrawal_create"))
        self.assertEqual(params["category"], ["tax"])

        back = urlparse(params["next"][0])
        self.assertEqual(back.path, reverse("tax_quarter_overview"))
        self.assertEqual(parse_qs(back.query)["year"], ["2024"])

    def test_add_payment_round_trip_lands_back_on_the_overview(self):
        """End to end: follow the link the page renders, save, and check where
        that leaves you — the two halves are wired in different modules."""
        add_url = self.client_instance.get(reverse("tax_quarter_overview") + "?year=2024").context[
            "add_payment_url"
        ]

        form_page = self.client_instance.get(add_url)
        self.assertEqual(form_page.status_code, 200)

        response = self.client_instance.post(
            add_url,
            {
                "description": "Tax prepayment Q1",
                "amount": "900.00",
                "category": "tax",
                "date": "2024-03-10",
                "next": form_page.context["next"],
            },
        )
        self.assertRedirects(
            response, reverse("tax_quarter_overview") + "?year=2024", fetch_redirect_response=False
        )
