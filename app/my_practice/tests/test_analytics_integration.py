"""
Integration tests for analytics functions using centralized session counting.
Ensures heatmap, busiest months, and top clients all use consistent calculations.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from my_practice.models import Client, Invoice, InvoiceItem, Practice, ServiceType, Session
from my_practice.utils.analytics_utils import ClientAnalyzer, SessionAnalyzer
from my_practice.utils.heatmap_utils import get_sessions_for_month


class HeatmapIntegrationTest(TestCase):
    """Tests for heatmap functionality with centralized session counting."""

    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="analytics_integration-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.client = Client.objects.create(
            client_code="HM",
            full_name="Heatmap Test",
            email="hm@example.com",
            hourly_rate_60=Decimal("90.00"),
            hourly_rate_90=Decimal("130.00"),
            practice=self.practice,
        )

        self.service_60 = ServiceType.objects.create(
            code="individual",
            name_en="Individual Session",
            name_de="Einzelsitzung",
            practice=self.practice,
        )

        self.service_90 = ServiceType.objects.create(
            code="double",
            name_en="Extended Session",
            name_de="Doppelsitzung",
            practice=self.practice,
        )

        self.service_cancel = ServiceType.objects.create(
            code="cancel_fee",
            name_en="Cancellation Fee",
            name_de="Ausfallgebühr",
            practice=self.practice,
        )

        # Create invoice for 2026 (uses InvoiceItems)
        self.invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="HM-1",
            invoice_date=date(2026, 3, 15),
            status="paid",
            practice=self.practice,
        )

    def test_heatmap_respects_quantity(self):
        """Test that heatmap correctly multiplies by quantity."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # 2 x 60min sessions = 2.0 hours
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_60,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2026, 3, 5),
                duration=60,
            ),
            rate=Decimal("90.00"),
            quantity=Decimal("2.00"),
        )

        month_data = get_sessions_for_month(date(2026, 3, 1))
        self.assertEqual(month_data["HM"], 2.0)

    def test_heatmap_respects_duration(self):
        """Test that heatmap correctly normalizes by duration."""
        # 90min session = 1.5 hours
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_90,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2026, 3, 10),
                duration=90,
            ),
            rate=Decimal("130.00"),
            quantity=Decimal("1.00"),
        )

        month_data = get_sessions_for_month(date(2026, 3, 1))
        self.assertEqual(month_data["HM"], 1.5)

    def test_heatmap_excludes_cancellations(self):
        """Test that heatmap excludes Ausfall items."""
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_60,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2026, 3, 5),
                duration=60,
            ),
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )

        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_cancel,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2026, 3, 12),
                duration=60,
            ),
            rate=Decimal("45.00"),
            quantity=Decimal("1.00"),
        )

        month_data = get_sessions_for_month(date(2026, 3, 1))
        self.assertEqual(month_data["HM"], 1.0)  # Only non-cancel counted

    def test_heatmap_mixed_clients(self):
        """Test heatmap with multiple clients."""
        client2 = Client.objects.create(
            client_code="HM2",
            full_name="Heatmap Test 2",
            email="hm2@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

        invoice2 = Invoice.objects.create(
            client=client2,
            invoice_number="HM2-1",
            invoice_date=date(2026, 3, 15),
            status="paid",
            practice=self.practice,
        )

        # HM: 1 x 60min = 1.0
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_60,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2026, 3, 5),
                duration=60,
            ),
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )

        # HM2: 1 x 90min = 1.5
        InvoiceItem.objects.create(
            invoice=invoice2,
            service_type=self.service_90,
            session=Session.objects.create(
                client=client2,
                session_date=date(2026, 3, 10),
                duration=90,
            ),
            rate=Decimal("130.00"),
            quantity=Decimal("1.00"),
        )

        month_data = get_sessions_for_month(date(2026, 3, 1))
        self.assertEqual(month_data["HM"], 1.0)
        self.assertEqual(month_data["HM2"], 1.5)


class BusiestMonthsIntegrationTest(TestCase):
    """Tests for busiest months analysis with centralized session counting."""

    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="analytics_integration-2",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.client = Client.objects.create(
            client_code="BM",
            full_name="Busiest Test",
            email="bm@example.com",
            hourly_rate_60=Decimal("90.00"),
            hourly_rate_90=Decimal("130.00"),
            practice=self.practice,
        )

        self.service_60 = ServiceType.objects.create(
            code="individual",
            name_en="Individual Session",
            name_de="Einzelsitzung",
            practice=self.practice,
        )

        self.service_90 = ServiceType.objects.create(
            code="double",
            name_en="Extended Session",
            name_de="Doppelsitzung",
            practice=self.practice,
        )

        self.service_cancel = ServiceType.objects.create(
            code="cancel_fee",
            name_en="Cancellation Fee",
            name_de="Ausfallgebühr",
            practice=self.practice,
        )

        # Create invoices for 2026
        self.invoice_feb = Invoice.objects.create(
            client=self.client,
            invoice_number="BM-FEB",
            invoice_date=date(2026, 2, 15),
            status="paid",
            practice=self.practice,
        )

        self.invoice_mar = Invoice.objects.create(
            client=self.client,
            invoice_number="BM-MAR",
            invoice_date=date(2026, 3, 15),
            status="paid",
            practice=self.practice,
        )

    def test_busiest_months_respects_quantity(self):
        """Test that busiest months correctly multiplies by quantity."""
        # February: 3 x 60min = 3.0 hours
        InvoiceItem.objects.create(
            invoice=self.invoice_feb,
            service_type=self.service_60,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2026, 2, 5),
                duration=60,
            ),
            rate=Decimal("90.00"),
            quantity=Decimal("3.00"),
        )

        # March: 1 x 60min = 1.0 hours
        InvoiceItem.objects.create(
            invoice=self.invoice_mar,
            service_type=self.service_60,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2026, 3, 5),
                duration=60,
            ),
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )

        result = SessionAnalyzer.get_busiest_months(start_year=2026)

        # February should be first (3.0 hours)
        self.assertEqual(result[0]["month_date"], date(2026, 2, 1))
        self.assertEqual(result[0]["session_hours"], 3.0)

        # March should be second (1.0 hours)
        self.assertEqual(result[1]["month_date"], date(2026, 3, 1))
        self.assertEqual(result[1]["session_hours"], 1.0)

    def test_busiest_months_respects_duration(self):
        """Test that busiest months correctly normalizes by duration."""
        # February: 2 x 90min = 3.0 hours
        InvoiceItem.objects.create(
            invoice=self.invoice_feb,
            service_type=self.service_90,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2026, 2, 5),
                duration=90,
            ),
            rate=Decimal("130.00"),
            quantity=Decimal("2.00"),
        )

        result = SessionAnalyzer.get_busiest_months(start_year=2026)

        feb_data = [m for m in result if m["month_date"] == date(2026, 2, 1)][0]
        self.assertEqual(feb_data["session_hours"], 3.0)

    def test_busiest_months_excludes_cancellations(self):
        """Test that busiest months excludes Ausfall items."""
        # Regular session
        InvoiceItem.objects.create(
            invoice=self.invoice_feb,
            service_type=self.service_60,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2026, 2, 5),
                duration=60,
            ),
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )

        # Cancellation (should be excluded)
        InvoiceItem.objects.create(
            invoice=self.invoice_feb,
            service_type=self.service_cancel,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2026, 2, 12),
                duration=60,
            ),
            rate=Decimal("45.00"),
            quantity=Decimal("1.00"),
        )

        result = SessionAnalyzer.get_busiest_months(start_year=2026)

        feb_data = [m for m in result if m["month_date"] == date(2026, 2, 1)][0]
        self.assertEqual(feb_data["session_hours"], 1.0)  # Only non-cancel counted


class TopClientsIntegrationTest(TestCase):
    """Tests for top clients ranking with centralized session counting."""

    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="analytics_integration-3",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.client_a = Client.objects.create(
            client_code="A",
            full_name="Client A",
            email="a@example.com",
            hourly_rate_60=Decimal("90.00"),
            hourly_rate_90=Decimal("130.00"),
            practice=self.practice,
        )

        self.client_b = Client.objects.create(
            client_code="B",
            full_name="Client B",
            email="b@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

        self.service_60 = ServiceType.objects.create(
            code="individual",
            name_en="Individual Session",
            name_de="Einzelsitzung",
            practice=self.practice,
        )

        self.service_90 = ServiceType.objects.create(
            code="double",
            name_en="Extended Session",
            name_de="Doppelsitzung",
            practice=self.practice,
        )

        self.service_cancel = ServiceType.objects.create(
            code="cancel_fee",
            name_en="Cancellation Fee",
            name_de="Ausfallgebühr",
            practice=self.practice,
        )

    def test_top_clients_respects_quantity(self):
        """Test that top clients correctly multiplies by quantity."""
        # Client A: 1 invoice with 3 x 60min sessions
        invoice_a = Invoice.objects.create(
            client=self.client_a,
            invoice_number="A-1",
            invoice_date=date(2026, 1, 15),
            status="paid",
            total=Decimal("270.00"),
            practice=self.practice,
        )

        InvoiceItem.objects.create(
            invoice=invoice_a,
            service_type=self.service_60,
            session=Session.objects.create(
                client=self.client_a,
                session_date=date(2026, 1, 5),
                duration=60,
            ),
            rate=Decimal("90.00"),
            quantity=Decimal("3.00"),
        )

        result = ClientAnalyzer.get_top_by_revenue(limit=10)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["client"], self.client_a)
        self.assertEqual(result[0]["session_hours"], 3.0)

    def test_top_clients_respects_duration(self):
        """Test that top clients correctly normalizes by duration."""
        # Client A: 2 x 90min sessions = 3.0 hours
        invoice_a = Invoice.objects.create(
            client=self.client_a,
            invoice_number="A-1",
            invoice_date=date(2026, 1, 15),
            status="paid",
            total=Decimal("260.00"),
            practice=self.practice,
        )

        InvoiceItem.objects.create(
            invoice=invoice_a,
            service_type=self.service_90,
            session=Session.objects.create(
                client=self.client_a,
                session_date=date(2026, 1, 5),
                duration=90,
            ),
            rate=Decimal("130.00"),
            quantity=Decimal("2.00"),
        )

        result = ClientAnalyzer.get_top_by_revenue(limit=10)

        self.assertEqual(result[0]["session_hours"], 3.0)

    def test_top_clients_excludes_cancellations(self):
        """Test that top clients excludes Ausfall items."""
        invoice_a = Invoice.objects.create(
            client=self.client_a,
            invoice_number="A-1",
            invoice_date=date(2026, 1, 15),
            status="paid",
            total=Decimal("180.00"),
            practice=self.practice,
        )

        # Regular session
        InvoiceItem.objects.create(
            invoice=invoice_a,
            service_type=self.service_60,
            session=Session.objects.create(
                client=self.client_a,
                session_date=date(2026, 1, 5),
                duration=60,
            ),
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )

        # Cancellation (should be excluded)
        InvoiceItem.objects.create(
            invoice=invoice_a,
            service_type=self.service_cancel,
            session=Session.objects.create(
                client=self.client_a,
                session_date=date(2026, 1, 12),
                duration=60,
            ),
            rate=Decimal("45.00"),
            quantity=Decimal("1.00"),
        )

        result = ClientAnalyzer.get_top_by_revenue(limit=10)

        self.assertEqual(result[0]["session_hours"], 1.0)  # Only non-cancel counted

    def test_top_clients_mixed_durations_and_quantities(self):
        """Test top clients with complex mix of durations and quantities."""
        # Client A: High revenue, complex sessions
        invoice_a = Invoice.objects.create(
            client=self.client_a,
            invoice_number="A-1",
            invoice_date=date(2026, 1, 15),
            status="paid",
            total=Decimal("580.00"),
            practice=self.practice,
        )

        # 2 x 60min = 2.0 hours
        InvoiceItem.objects.create(
            invoice=invoice_a,
            service_type=self.service_60,
            session=Session.objects.create(
                client=self.client_a,
                session_date=date(2026, 1, 5),
                duration=60,
            ),
            rate=Decimal("90.00"),
            quantity=Decimal("2.00"),
        )

        # 2 x 90min = 3.0 hours
        InvoiceItem.objects.create(
            invoice=invoice_a,
            service_type=self.service_90,
            session=Session.objects.create(
                client=self.client_a,
                session_date=date(2026, 1, 12),
                duration=90,
            ),
            rate=Decimal("130.00"),
            quantity=Decimal("2.00"),
        )

        # Client B: Lower revenue, fewer sessions
        invoice_b = Invoice.objects.create(
            client=self.client_b,
            invoice_number="B-1",
            invoice_date=date(2026, 1, 15),
            status="paid",
            total=Decimal("90.00"),
            practice=self.practice,
        )

        # 1 x 60min = 1.0 hours
        InvoiceItem.objects.create(
            invoice=invoice_b,
            service_type=self.service_60,
            session=Session.objects.create(
                client=self.client_b,
                session_date=date(2026, 1, 8),
                duration=60,
            ),
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )

        result = ClientAnalyzer.get_top_by_revenue(limit=10)

        # Should be sorted by revenue (A first)
        self.assertEqual(result[0]["client"], self.client_a)
        self.assertEqual(result[0]["session_hours"], 5.0)  # 2.0 + 3.0

        self.assertEqual(result[1]["client"], self.client_b)
        self.assertEqual(result[1]["session_hours"], 1.0)

    def test_top_clients_only_counts_paid_invoices(self):
        """Test that only paid invoices are counted."""
        # Paid invoice
        invoice_paid = Invoice.objects.create(
            client=self.client_a,
            invoice_number="A-1",
            invoice_date=date(2026, 1, 15),
            status="paid",
            total=Decimal("90.00"),
            practice=self.practice,
        )

        InvoiceItem.objects.create(
            invoice=invoice_paid,
            service_type=self.service_60,
            session=Session.objects.create(
                client=self.client_a,
                session_date=date(2026, 1, 5),
                duration=60,
            ),
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )

        # Unpaid invoice (should be excluded)
        invoice_unpaid = Invoice.objects.create(
            client=self.client_a,
            invoice_number="A-2",
            invoice_date=date(2026, 2, 15),
            status="sent",
            total=Decimal("90.00"),
            practice=self.practice,
        )

        InvoiceItem.objects.create(
            invoice=invoice_unpaid,
            service_type=self.service_60,
            session=Session.objects.create(
                client=self.client_a,
                session_date=date(2026, 2, 5),
                duration=60,
            ),
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )

        result = ClientAnalyzer.get_top_by_revenue(limit=10)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["session_hours"], 1.0)  # Only paid invoice counted
