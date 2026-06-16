"""
Tests for analytics utility classes.
Tests the refactored class-based analytics utilities.
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
    """Test RevenueAnalyzer class"""

    def setUp(self):
        """Create test fixtures"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="analytics_classes-1",
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

    def test_get_monthly_trends_returns_correct_format(self):
        """Test that get_monthly_trends returns properly formatted data"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Create test invoice
        Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-1",
            invoice_date=date.today(),
            paid_date=date.today(),
            status="paid",
            total=Decimal("90.00"),
            practice=self.practice,
        )

        trends = RevenueAnalyzer.get_monthly_trends(
            start_year=date.today().year, end_date=date.today()
        )

        self.assertIsInstance(trends, list)
        self.assertGreater(len(trends), 0)

        # Check data structure
        for item in trends:
            self.assertIn("month", item)
            self.assertIn("month_name", item)
            self.assertIn("year", item)
            self.assertIn("revenue", item)
            self.assertIn("date", item)

    def test_get_monthly_trends_with_no_data(self):
        """Test that get_monthly_trends works with no invoices"""
        trends = RevenueAnalyzer.get_monthly_trends(
            start_year=date.today().year, end_date=date.today()
        )

        self.assertIsInstance(trends, list)
        # Should still return months, just with 0 revenue
        self.assertGreater(len(trends), 0)
        self.assertEqual(trends[0]["revenue"], 0.0)

    def test_get_yearly_comparison_includes_all_years(self):
        """Test that yearly comparison includes all requested years"""
        # Create invoices in different years
        Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-2020",
            invoice_date=date(2020, 6, 1),
            paid_date=date(2020, 6, 1),
            status="paid",
            total=Decimal("100.00"),
            practice=self.practice,
        )

        Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-2021",
            invoice_date=date(2021, 6, 1),
            paid_date=date(2021, 6, 1),
            status="paid",
            total=Decimal("200.00"),
            practice=self.practice,
        )

        comparison = RevenueAnalyzer.get_yearly_comparison(start_year=2020)

        self.assertIsInstance(comparison, list)
        years = [item["year"] for item in comparison]
        self.assertIn(2020, years)
        self.assertIn(2021, years)


class SessionAnalyzerTests(TestCase):
    """Test SessionAnalyzer class"""

    def setUp(self):
        """Create test fixtures"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="analytics_classes-2",
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

        self.service_type_60 = ServiceType.objects.create(
            code="test_60",
            name="Test 60min",
            name_de="Test 60 Min",
            default_duration=60,
            practice=self.practice,
        )

        self.service_type_90 = ServiceType.objects.create(
            code="test_90",
            name="Test 90min",
            name_de="Test 90 Min",
            default_duration=90,
            practice=self.practice,
        )

    def test_get_type_distribution_empty(self):
        """Test session type distribution with no data"""
        result = SessionAnalyzer.get_type_distribution()

        self.assertEqual(result["total"], 0)
        self.assertEqual(result["types"], [])

    def test_get_type_distribution_with_sessions(self):
        """Test session type distribution with actual sessions"""
        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-1",
            invoice_date=date.today(),
            status="paid",
            total=Decimal("180.00"),
            practice=self.practice,
        )

        # Create 60min session
        session_60 = Session.objects.create(
            client=self.client,
            session_date=date.today(),
            duration=60,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            session=session_60,
            service_type=self.service_type_60,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
            total=Decimal("90.00"),
        )

        # Create 90min session
        session_90 = Session.objects.create(
            client=self.client,
            session_date=date.today(),
            duration=90,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            session=session_90,
            service_type=self.service_type_90,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
            total=Decimal("90.00"),
        )

        result = SessionAnalyzer.get_type_distribution()

        self.assertEqual(result["total"], 2)
        self.assertIn("types", result)
        self.assertGreater(len(result["types"]), 0)


class ClientAnalyzerTests(TestCase):
    """Test ClientAnalyzer class"""

    def setUp(self):
        """Create test fixtures"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="analytics_classes-3",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.client1 = Client.objects.create(
            client_code="CL1",
            full_name="Client One",
            email="client1@example.com",
            language="de",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

        self.client2 = Client.objects.create(
            client_code="CL2",
            full_name="Client Two",
            email="client2@example.com",
            language="de",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

    def test_get_top_by_revenue_empty(self):
        """Test top clients with no invoices"""
        result = ClientAnalyzer.get_top_by_revenue(limit=10)

        self.assertEqual(len(result), 0)

    def test_get_top_by_revenue_ordering(self):
        """Test that clients are ordered by revenue"""
        # Client 1: 200 EUR
        Invoice.objects.create(
            client=self.client1,
            invoice_number="CL1-1",
            invoice_date=date.today(),
            status="paid",
            total=Decimal("200.00"),
            practice=self.practice,
        )

        # Client 2: 500 EUR
        Invoice.objects.create(
            client=self.client2,
            invoice_number="CL2-1",
            invoice_date=date.today(),
            status="paid",
            total=Decimal("500.00"),
            practice=self.practice,
        )

        result = ClientAnalyzer.get_top_by_revenue(limit=10)

        self.assertEqual(len(result), 2)
        # Client 2 should be first (higher revenue)
        self.assertEqual(result[0]["client"].client_code, "CL2")
        self.assertEqual(result[1]["client"].client_code, "CL1")
        self.assertEqual(result[0]["total_revenue"], 500.0)

    def test_get_top_by_revenue_respects_limit(self):
        """Test that limit parameter works"""
        # Create 3 clients with invoices
        for i in range(3):
            client = Client.objects.create(
                client_code=f"CL{i + 10}",
                full_name=f"Client {i + 10}",
                email=f"client{i + 10}@example.com",
                language="de",
                hourly_rate_60=Decimal("90.00"),
                practice=self.practice,
            )
            Invoice.objects.create(
                client=client,
                invoice_number=f"CL{i + 10}-1",
                invoice_date=date.today(),
                status="paid",
                total=Decimal("100.00"),
                practice=self.practice,
            )

        result = ClientAnalyzer.get_top_by_revenue(limit=2)

        self.assertEqual(len(result), 2)


class ExpenseAnalyzerTests(TestCase):
    """Test ExpenseAnalyzer class"""

    def setUp(self):
        """Create test practice"""
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="analytics-expense",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

    def test_get_monthly_trends_returns_correct_structure(self):
        """Test monthly expense trends structure"""
        trends = ExpenseAnalyzer.get_monthly_trends(
            start_year=date.today().year, end_date=date.today()
        )

        self.assertIsInstance(trends, list)
        self.assertGreater(len(trends), 0)

        for item in trends:
            self.assertIn("month", item)
            self.assertIn("expenses", item)
            self.assertIn("year", item)

    def test_get_category_breakdown_with_no_expenses(self):
        """Test category breakdown with no data"""
        result = ExpenseAnalyzer.get_expense_breakdown()

        self.assertEqual(result["total"], 0)
        self.assertEqual(result["categories"], [])

    def test_get_category_breakdown_with_expenses(self):
        """Test category breakdown with actual expenses"""
        CompanyExpense.objects.create(
            date=date.today(),
            amount=Decimal("100.00"),
            category="software",
            practice=self.practice,
        )

        CompanyExpense.objects.create(
            date=date.today(),
            amount=Decimal("200.00"),
            category="miete",
            practice=self.practice,
        )

        result = ExpenseAnalyzer.get_expense_breakdown()

        self.assertEqual(result["total"], 300.0)
        self.assertEqual(len(result["categories"]), 2)
        # Should be ordered by amount descending
        self.assertEqual(result["categories"][0]["amount"], 200.0)


class ProfitCalculatorTests(TestCase):
    """Test ProfitCalculator class"""

    def setUp(self):
        """Create test fixtures"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="analytics_classes-4",
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
            practice=self.practice,
        )

    def test_calculate_yearly_basic(self):
        """Test basic profit calculation"""
        # Use a fixed past year to avoid issues with future dates in current year
        year = 2023

        # Revenue
        Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-1",
            invoice_date=date(year, 6, 1),
            paid_date=date(year, 6, 1),
            status="paid",
            total=Decimal("1000.00"),
            practice=self.practice,
        )

        # Expense
        CompanyExpense.objects.create(
            date=date(year, 6, 1),
            amount=Decimal("300.00"),
            category="software",
            practice=self.practice,
        )

        # Withdrawal
        CompanyWithdrawal.objects.create(
            date=date(year, 6, 1),
            amount=Decimal("200.00"),
            category="salary",
            practice=self.practice,
        )

        result = ProfitCalculator.calculate_yearly(start_year=year, end_year=year)

        self.assertEqual(len(result), 1)
        year_data = result[0]

        self.assertEqual(year_data["revenue"], 1000.0)
        self.assertEqual(year_data["expenses"], 300.0)
        self.assertEqual(year_data["profit"], 700.0)  # 1000 - 300
        self.assertEqual(year_data["withdrawals"], 200.0)

    def test_calculate_yearly_cumulative_profit(self):
        """Test cumulative profit calculation across years"""
        # Year 1: 500 profit
        Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-2020",
            invoice_date=date(2020, 6, 1),
            paid_date=date(2020, 6, 1),
            status="paid",
            total=Decimal("800.00"),
            practice=self.practice,
        )
        CompanyExpense.objects.create(
            date=date(2020, 6, 1),
            amount=Decimal("300.00"),
            category="software",
            practice=self.practice,
        )

        # Year 2: 400 profit
        Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-2021",
            invoice_date=date(2021, 6, 1),
            paid_date=date(2021, 6, 1),
            status="paid",
            total=Decimal("600.00"),
            practice=self.practice,
        )
        CompanyExpense.objects.create(
            date=date(2021, 6, 1),
            amount=Decimal("200.00"),
            category="software",
            practice=self.practice,
        )

        result = ProfitCalculator.calculate_yearly(start_year=2020, end_year=2021)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["cumulative_profit"], 500.0)
        self.assertEqual(result[1]["cumulative_profit"], 900.0)  # 500 + 400


class AnalyzerAPITests(TestCase):
    """Test that analyzer class APIs work correctly"""

    def test_analyzer_class_methods_work(self):
        """Test that class-based methods return expected types"""
        from ..utils.analytics_utils import (
            ClientAnalyzer,
            ExpenseAnalyzer,
            ProfitCalculator,
            RevenueAnalyzer,
            SessionAnalyzer,
        )

        # Just check they're callable and return expected types
        self.assertIsInstance(RevenueAnalyzer.get_monthly_trends(), list)
        self.assertIsInstance(SessionAnalyzer.get_type_distribution(), dict)
        self.assertIsInstance(ClientAnalyzer.get_top_by_revenue(), list)
        self.assertIsInstance(SessionAnalyzer.get_busiest_months(), list)
        self.assertIsInstance(RevenueAnalyzer.get_yearly_comparison(), list)
        self.assertIsInstance(ExpenseAnalyzer.get_monthly_trends(), list)
        self.assertIsInstance(ExpenseAnalyzer.get_expense_breakdown(), dict)
        self.assertIsInstance(ProfitCalculator.calculate_yearly(), list)
