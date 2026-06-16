"""
Tests for analytics_utils analyzer classes.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from ..models import (
    Client,
    CompanyExpense,
    CompanyWithdrawal,
    Invoice,
    InvoiceItem,
    Practice,
    ServiceType,
    Session,
)
from ..utils.analytics_utils import (
    ClientAnalyzer,
    ExpenseAnalyzer,
    ProfitCalculator,
    RevenueAnalyzer,
    SessionAnalyzer,
)


class RevenueAnalyzerTests(TestCase):
    """Tests for RevenueAnalyzer class"""

    def setUp(self):
        """Create test fixtures"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="analytics_utils-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.client = Client.objects.create(
            client_code="TEST",
            full_name="Test Client",
            email="test@example.com",
            language="de",
            hourly_rate_60=Decimal("90.00"),
            hourly_rate_90=Decimal("130.00"),
            practice=self.practice,
        )

        # Create invoices for different months
        Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-1",
            invoice_date=date(2025, 1, 15),
            paid_date=date(2025, 1, 20),
            status="paid",
            total=Decimal("180.00"),
            practice=self.practice,
        )

        Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-2",
            invoice_date=date(2025, 2, 15),
            paid_date=date(2025, 2, 20),
            status="paid",
            total=Decimal("270.00"),
            practice=self.practice,
        )

    def test_get_monthly_trends(self):
        """Test monthly revenue trends calculation"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        trends = RevenueAnalyzer.get_monthly_trends(start_year=2025, end_date=date(2025, 2, 28))

        # Should return data for January and February
        self.assertEqual(len(trends), 2)

        # Check January revenue (use month_name for reliable matching)
        jan_data = [t for t in trends if t["year"] == 2025 and t["month_name"] == "January"][0]
        self.assertEqual(jan_data["revenue"], 180.0)

        # Check February revenue
        feb_data = [t for t in trends if t["year"] == 2025 and t["month_name"] == "February"][0]
        self.assertEqual(feb_data["revenue"], 270.0)

    def test_get_yearly_comparison(self):
        """Test yearly comparison calculation"""
        # Create expense and withdrawal
        CompanyExpense.objects.create(
            date=date(2025, 1, 15),
            amount=Decimal("50.00"),
            category="software",
            practice=self.practice,
        )

        CompanyWithdrawal.objects.create(
            date=date(2025, 1, 20),
            amount=Decimal("100.00"),
            category="salary",
            practice=self.practice,
        )

        comparison = RevenueAnalyzer.get_yearly_comparison(start_year=2025)

        # Should have 2025 data
        data_2025 = [d for d in comparison if d["year"] == 2025][0]

        self.assertEqual(data_2025["revenue"], 450.0)  # 180 + 270
        self.assertEqual(data_2025["expenses"], 50.0)
        self.assertEqual(data_2025["withdrawals"], 100.0)
        self.assertEqual(data_2025["remaining"], 300.0)  # 450 - 50 - 100


class SessionAnalyzerTests(TestCase):
    """Tests for SessionAnalyzer class"""

    def setUp(self):
        """Create test fixtures"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="analytics_utils-2",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.client = Client.objects.create(
            client_code="TEST",
            full_name="Test Client",
            email="test@example.com",
            language="de",
            practice=self.practice,
        )

        self.service_60 = ServiceType.objects.create(
            code="therapy_60",
            name="60-Min Session",
            default_duration=60,
            practice=self.practice,
        )

        self.service_90 = ServiceType.objects.create(
            code="therapy_90",
            name="90-Min Session",
            default_duration=90,
            practice=self.practice,
        )

        # Create invoice with items
        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-1",
            invoice_date=date.today(),
            status="paid",
            total=Decimal("180.00"),
            practice=self.practice,
        )

        session_60 = Session.objects.create(
            client=self.client,
            session_date=date.today(),
            duration=60,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            session=session_60,
            service_type=self.service_60,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
            total=Decimal("90.00"),
        )

        session_90 = Session.objects.create(
            client=self.client,
            session_date=date.today(),
            duration=90,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            session=session_90,
            service_type=self.service_90,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
            total=Decimal("90.00"),
        )

    def test_get_type_distribution(self):
        """Test session type distribution calculation"""
        distribution = SessionAnalyzer.get_type_distribution()

        self.assertEqual(distribution["total"], 2)
        self.assertIn("types", distribution)

        # Should have 60-min and 90-min sessions
        types = distribution["types"]
        self.assertIn("60-Min Sitzungen", types)
        self.assertIn("90-Min Sitzungen", types)


class ClientAnalyzerTests(TestCase):
    """Tests for ClientAnalyzer class"""

    def setUp(self):
        """Create test fixtures"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="analytics_utils-3",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.client1 = Client.objects.create(
            client_code="CL1",
            full_name="Client One",
            email="client1@example.com",
            language="de",
            practice=self.practice,
        )

        self.client2 = Client.objects.create(
            client_code="CL2",
            full_name="Client Two",
            email="client2@example.com",
            language="en",
            practice=self.practice,
        )

        self.service = ServiceType.objects.create(
            code="therapy_60",
            name="60-Min Session",
            default_duration=60,
            practice=self.practice,
        )

        # Client 1: Higher revenue (500€ via items)
        invoice1 = Invoice.objects.create(
            client=self.client1,
            invoice_number="CL1-1",
            invoice_date=date.today(),
            status="paid",
            practice=self.practice,
        )

        # Create items totaling 500€
        for i in range(5):
            session = Session.objects.create(
                client=self.client1,
                session_date=date.today(),
                duration=60,
            )
            InvoiceItem.objects.create(
                invoice=invoice1,
                session=session,
                service_type=self.service,
                rate=Decimal("100.00"),
                quantity=Decimal("1.00"),
                total=Decimal("100.00"),
            )

        # Client 2: Lower revenue (200€ via items)
        invoice2 = Invoice.objects.create(
            client=self.client2,
            invoice_number="CL2-1",
            invoice_date=date.today(),
            status="paid",
            practice=self.practice,
        )

        # Create items totaling 200€
        for i in range(2):
            session = Session.objects.create(
                client=self.client2,
                session_date=date.today(),
                duration=60,
            )
            InvoiceItem.objects.create(
                invoice=invoice2,
                session=session,
                service_type=self.service,
                rate=Decimal("100.00"),
                quantity=Decimal("1.00"),
                total=Decimal("100.00"),
            )

    def test_get_top_by_revenue(self):
        """Test top clients by revenue ranking"""
        top_clients = ClientAnalyzer.get_top_by_revenue(limit=2)

        self.assertEqual(len(top_clients), 2)

        # First should be client1 with higher revenue
        self.assertEqual(top_clients[0]["client"].client_code, "CL1")
        self.assertEqual(top_clients[0]["total_revenue"], 500.0)

        # Second should be client2
        self.assertEqual(top_clients[1]["client"].client_code, "CL2")
        self.assertEqual(top_clients[1]["total_revenue"], 200.0)


class ExpenseAnalyzerTests(TestCase):
    """Tests for ExpenseAnalyzer class"""

    def setUp(self):
        """Create test fixtures"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="analytics_utils-4",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Note: All expenses are dated on any day but aggregated by year
        # The system distributes yearly totals equally across 12 months
        CompanyExpense.objects.create(
            date=date(2025, 12, 31),  # Standard expense date
            amount=Decimal("100.00"),
            category="software",
            is_tax_deductible=True,
            practice=self.practice,
        )

        CompanyExpense.objects.create(
            date=date(2025, 12, 31),  # Standard expense date
            amount=Decimal("50.00"),
            category="materialien",
            is_tax_deductible=True,
            practice=self.practice,
        )

    def test_get_monthly_trends(self):
        """
        Test monthly expense trends.
        Expenses are distributed equally across all months of the year.
        Total: 150.00 / 12 months = 12.50 per month
        """
        trends = ExpenseAnalyzer.get_monthly_trends(start_year=2025, end_date=date(2025, 2, 28))

        self.assertEqual(len(trends), 2)

        # Each month should have 150/12 = 12.50
        expected_monthly = 12.5

        # Check January
        jan_data = [t for t in trends if t["month_name"] == "January"][0]
        self.assertAlmostEqual(jan_data["expenses"], expected_monthly, places=2)

        # Check February
        feb_data = [t for t in trends if t["month_name"] == "February"][0]
        self.assertAlmostEqual(feb_data["expenses"], expected_monthly, places=2)

    def test_get_category_breakdown(self):
        """Test expense category breakdown"""
        breakdown = ExpenseAnalyzer.get_expense_breakdown()

        self.assertEqual(breakdown["total"], 150.0)
        self.assertEqual(len(breakdown["categories"]), 2)

        # Software should be first (higher amount)
        first_category = breakdown["categories"][0]
        self.assertEqual(first_category["amount"], 100.0)
        self.assertEqual(first_category["percentage"], 66.7)


class ProfitCalculatorTests(TestCase):
    """Tests for ProfitCalculator class"""

    def setUp(self):
        """Create test fixtures"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="analytics_utils-5",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        client = Client.objects.create(
            client_code="TEST",
            full_name="Test Client",
            email="test@example.com",
            language="de",
            practice=self.practice,
        )

        Invoice.objects.create(
            client=client,
            invoice_number="TEST-1",
            invoice_date=date(2025, 1, 15),
            paid_date=date(2025, 1, 20),
            status="paid",
            total=Decimal("1000.00"),
            practice=self.practice,
        )

        CompanyExpense.objects.create(
            date=date(2025, 1, 15),
            amount=Decimal("300.00"),
            category="software",
            practice=self.practice,
        )

        CompanyWithdrawal.objects.create(
            date=date(2025, 1, 20),
            amount=Decimal("200.00"),
            category="salary",
            practice=self.practice,
        )

    def test_calculate_yearly(self):
        """Test yearly profit calculation"""
        profit_data = ProfitCalculator.calculate_yearly(start_year=2025, end_year=2025)

        self.assertEqual(len(profit_data), 1)

        year_data = profit_data[0]
        self.assertEqual(year_data["year"], 2025)
        self.assertEqual(year_data["revenue"], 1000.0)
        self.assertEqual(year_data["expenses"], 300.0)
        self.assertEqual(year_data["profit"], 700.0)  # 1000 - 300
        self.assertEqual(year_data["withdrawals"], 200.0)
        self.assertEqual(year_data["cumulative_profit"], 700.0)
