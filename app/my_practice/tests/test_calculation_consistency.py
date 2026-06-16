"""
Consistency tests for calculations across different views and methods.

These tests ensure that session counts, revenue totals, and other metrics
are calculated consistently regardless of which view or method is used.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from my_practice.models import (
    Client,
    Invoice,
    InvoiceItem,
    Practice,
    ServiceType,
    Session,
)
from my_practice.utils import count_sessions
from my_practice.utils.analytics_utils import ClientAnalyzer
from my_practice.utils.capacity_helpers import _get_booked_hours
from my_practice.utils.chart_helpers import aggregate_invoice_items_by_month
from my_practice.utils.heatmap_utils import get_sessions_for_month
from my_practice.utils.revenue_helpers import RevenueCalculator


class SessionCountConsistencyTests(TestCase):
    """Test that session counts are consistent across different calculation methods."""

    def setUp(self):
        """Create test data with known session counts."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="calculation_consistency-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.service_type = ServiceType.objects.create(
            code="individual",
            name="60 Min Session",
            name_de="60 Min. Psychotherapie",
            practice=self.practice,
        )

        self.client = Client.objects.create(
            client_code="TEST",
            full_name="Test Client",
            email="test@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

        # Create invoice with varied durations and quantities
        self.invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-001",
            invoice_date=date(2025, 6, 15),
            status="paid",
            total=Decimal("315.00"),
            practice=self.practice,
        )

        # Add items with different durations
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2025, 6, 10),
                duration=60,
            ),
            quantity=1,
            rate=Decimal("90.00"),
            total=Decimal("90.00"),
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2025, 6, 17),
                duration=90,
            ),
            quantity=1,
            rate=Decimal("135.00"),
            total=Decimal("135.00"),
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2025, 6, 24),
                duration=60,
            ),
            quantity=1,
            rate=Decimal("90.00"),
            total=Decimal("90.00"),
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2025, 6, 25),
                duration=30,
            ),
            quantity=1,
            rate=Decimal("45.00"),
            total=Decimal("45.00"),
        )

        # Expected: 1.0 + 1.5 + 1.0 + 0.5 = 4.0 hours (one Session per InvoiceItem)

    def test_count_sessions_direct(self):
        """Test direct count_sessions() call."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        items = InvoiceItem.objects.filter(invoice=self.invoice)
        sessions = count_sessions(items, exclude_cancellations=True)
        self.assertEqual(sessions, 4.0)

    def test_aggregate_invoice_items_by_month(self):
        """Test chart_helpers aggregation."""
        items = InvoiceItem.objects.filter(invoice=self.invoice)
        monthly_data = aggregate_invoice_items_by_month(items, exclude_cancellations=True)

        self.assertIn("2025-06", monthly_data)
        self.assertEqual(monthly_data["2025-06"], 4.0)

    def test_capacity_helpers_booked_hours(self):
        """Test capacity helpers calculation."""
        booked = _get_booked_hours(date(2025, 6, 1), date(2025, 6, 30))
        self.assertEqual(booked, 4.0)

    def test_heatmap_sessions_for_month(self):
        """Test heatmap calculation (for months >= 2026)."""
        # Create data in 2026 (after cutoff)
        invoice_2026 = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-002",
            invoice_date=date(2026, 1, 15),
            status="paid",
            total=Decimal("180.00"),
            practice=self.practice,
        )
        InvoiceItem.objects.create(
            invoice=invoice_2026,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2026, 1, 10),
                duration=60,
            ),
            quantity=2,
            rate=Decimal("90.00"),
            total=Decimal("180.00"),
        )

        sessions = get_sessions_for_month(date(2026, 1, 1))
        self.assertIn("TEST", sessions)
        self.assertEqual(sessions["TEST"], 2.0)

    def test_all_methods_agree(self):
        """Test that all calculation methods produce the same result."""
        items = InvoiceItem.objects.filter(invoice=self.invoice)

        # Method 1: Direct count_sessions
        direct = count_sessions(items, exclude_cancellations=True)

        # Method 2: Chart helpers
        monthly = aggregate_invoice_items_by_month(items, exclude_cancellations=True)
        chart_total = sum(monthly.values())

        # Method 3: Capacity helpers
        capacity = _get_booked_hours(date(2025, 6, 1), date(2025, 6, 30))

        # All should be equal
        self.assertEqual(direct, 4.0)
        self.assertEqual(chart_total, 4.0)
        self.assertEqual(capacity, 4.0)


class RevenueConsistencyTests(TestCase):
    """Test that revenue calculations are consistent across different views."""

    def setUp(self):
        """Create test data with known revenue."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="calculation_consistency-2",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.service_type = ServiceType.objects.create(
            code="individual", name="60 Min Session", practice=self.practice
        )

        self.client1 = Client.objects.create(
            client_code="C1",
            full_name="Client One",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        self.client2 = Client.objects.create(
            client_code="C2",
            full_name="Client Two",
            hourly_rate_60=Decimal("100.00"),
            practice=self.practice,
        )

        # Client 1: 2 paid invoices
        for i in range(2):
            invoice = Invoice.objects.create(
                client=self.client1,
                invoice_number=f"C1-{i + 1}",
                invoice_date=date(2025, 6, i + 1),
                status="paid",
                paid_date=date(2025, 6, i + 5),
                total=Decimal("90.00"),
                practice=self.practice,
            )
            InvoiceItem.objects.create(
                invoice=invoice,
                service_type=self.service_type,
                session=Session.objects.create(
                    client=self.client1,
                    session_date=date(2025, 6, i + 1),
                    duration=60,
                ),
                quantity=1,
                rate=Decimal("90.00"),
                total=Decimal("90.00"),
            )

        # Client 2: 1 paid invoice
        invoice = Invoice.objects.create(
            client=self.client2,
            invoice_number="C2-1",
            invoice_date=date(2025, 6, 10),
            status="paid",
            paid_date=date(2025, 6, 15),
            total=Decimal("100.00"),
            practice=self.practice,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client2,
                session_date=date(2025, 6, 10),
                duration=60,
            ),
            quantity=1,
            rate=Decimal("100.00"),
            total=Decimal("100.00"),
        )

        # Expected totals: C1=180, C2=100, Total=280

    def test_revenue_calculator_total_revenue(self):
        """Test RevenueCalculator.get_total_revenue()."""
        total = RevenueCalculator.get_total_revenue()
        self.assertEqual(total, Decimal("280.00"))

    def test_revenue_calculator_client_revenue(self):
        """Test RevenueCalculator.get_client_revenue()."""
        c1_stats = RevenueCalculator.get_client_revenue(self.client1)
        c2_stats = RevenueCalculator.get_client_revenue(self.client2)

        self.assertEqual(c1_stats["total"], Decimal("180.00"))
        self.assertEqual(c1_stats["count"], 2)

        self.assertEqual(c2_stats["total"], Decimal("100.00"))
        self.assertEqual(c2_stats["count"], 1)

    def test_revenue_calculator_year_revenue(self):
        """Test RevenueCalculator.get_year_revenue()."""
        year_stats = RevenueCalculator.get_year_revenue(2025, use_paid_date=True)
        self.assertEqual(year_stats["total"], Decimal("280.00"))

    def test_client_analyzer_top_by_revenue(self):
        """Test ClientAnalyzer.get_top_by_revenue()."""
        top_clients = ClientAnalyzer.get_top_by_revenue(limit=10)

        self.assertEqual(len(top_clients), 2)
        self.assertEqual(top_clients[0]["client"], self.client1)
        self.assertEqual(top_clients[0]["total_revenue"], 180.0)
        self.assertEqual(top_clients[1]["client"], self.client2)
        self.assertEqual(top_clients[1]["total_revenue"], 100.0)

    def test_all_revenue_methods_agree(self):
        """Test that all revenue methods produce consistent results."""
        # Method 1: Total revenue
        total_revenue = RevenueCalculator.get_total_revenue()

        # Method 2: Sum of individual clients
        c1_revenue = RevenueCalculator.get_client_revenue(self.client1)["total"]
        c2_revenue = RevenueCalculator.get_client_revenue(self.client2)["total"]
        sum_of_clients = c1_revenue + c2_revenue

        # Method 3: Year revenue
        year_revenue = RevenueCalculator.get_year_revenue(2025, use_paid_date=True)["total"]

        # All should be equal
        self.assertEqual(total_revenue, Decimal("280.00"))
        self.assertEqual(sum_of_clients, Decimal("280.00"))
        self.assertEqual(year_revenue, Decimal("280.00"))


class ClientViewsConsistencyTests(TestCase):
    """Test that client-related views show consistent data."""

    def setUp(self):
        """Create test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="calculation_consistency-3",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.user = User.objects.create_user(username="testuser", password="testpass123")

        self.service_type = ServiceType.objects.create(
            code="individual", name="60 Min Session", practice=self.practice
        )

        self.client = Client.objects.create(
            client_code="TEST",
            full_name="Test Client",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

        # Create 3 paid invoices with different session counts
        for i in range(3):
            invoice = Invoice.objects.create(
                client=self.client,
                invoice_number=f"TEST-{i + 1}",
                invoice_date=date(2025, 6, (i * 7) + 1),
                status="paid",
                paid_date=date(2025, 6, (i * 7) + 5),
                total=Decimal("135.00"),
                practice=self.practice,
            )
            # Each invoice has 1.5 hours (90 min)
            InvoiceItem.objects.create(
                invoice=invoice,
                service_type=self.service_type,
                session=Session.objects.create(
                    client=self.client,
                    session_date=date(2025, 6, (i * 7) + 1),
                    duration=90,
                ),
                quantity=1,
                rate=Decimal("135.00"),
                total=Decimal("135.00"),
            )

        # Expected: 3 invoices × 1.5h = 4.5h total

    def test_client_list_view_data(self):
        """Test that ClientListView shows correct aggregated data."""

        # Simulate the queryset used in ClientListView

        clients = Client.objects.annotate(
            total_revenue=RevenueCalculator.get_client_revenue_subquery(),
            total_sessions=RevenueCalculator.get_client_sessions_subquery(),
        ).filter(pk=self.client.pk)

        client = clients.first()
        self.assertEqual(client.total_revenue, Decimal("405.00"))  # 3 × 135
        # Fixed: 3 items × 90min × quantity 1 = 3 × 1.5h = 4.5 sessions
        self.assertEqual(float(client.total_sessions or 0), 4.5)

    def test_client_detail_view_data(self):
        """Test that client_detail() shows correct calculated data."""
        items = InvoiceItem.objects.filter(invoice__client=self.client, invoice__status="paid")

        total_hours = count_sessions(items, exclude_cancellations=True)
        self.assertEqual(total_hours, 4.5)  # 3 × 1.5h

    def test_client_data_consistency(self):
        """Test that client data is consistent between list and detail views."""
        # List view aggregation
        clients = Client.objects.annotate(
            total_revenue=RevenueCalculator.get_client_revenue_subquery(),
        ).filter(pk=self.client.pk)
        list_revenue = clients.first().total_revenue

        # Detail view calculation
        detail_stats = RevenueCalculator.get_client_revenue(self.client)
        detail_revenue = detail_stats["total"]

        # Should be equal
        self.assertEqual(list_revenue, detail_revenue)
        self.assertEqual(detail_revenue, Decimal("405.00"))


class CancellationHandlingConsistencyTests(TestCase):
    """Test that cancellations are handled consistently across all methods."""

    def setUp(self):
        """Create test data with cancellations."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="calculation_consistency-5",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.service_type = ServiceType.objects.create(
            code="individual", name="60 Min Session", practice=self.practice
        )

        self.cancel_service_type = ServiceType.objects.create(
            code="cancel_fee", name="Cancellation Fee", practice=self.practice
        )

        self.client = Client.objects.create(
            client_code="CANC", full_name="Cancellation Test", practice=self.practice
        )

        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="CANC-001",
            invoice_date=date(2025, 6, 15),
            status="paid",
            total=Decimal("180.00"),
            practice=self.practice,
        )

        # Regular session
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2025, 6, 1),
                duration=60,
            ),
            quantity=1,
            rate=Decimal("90.00"),
            total=Decimal("90.00"),
        )

        # Cancellation fee item
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.cancel_service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2025, 6, 8),
                duration=60,
            ),
            quantity=1,
            rate=Decimal("45.00"),
            total=Decimal("45.00"),
        )

        # Another regular session
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2025, 6, 15),
                duration=60,
            ),
            quantity=1,
            rate=Decimal("90.00"),
            total=Decimal("90.00"),
        )

        # Expected: 2 sessions (excluding cancellation)

    def test_count_sessions_excludes_cancellations(self):
        """Test that count_sessions excludes cancellations by default."""
        items = InvoiceItem.objects.filter(invoice__client=self.client)

        with_cancellations = count_sessions(items, exclude_cancellations=False)
        without_cancellations = count_sessions(items, exclude_cancellations=True)

        self.assertEqual(with_cancellations, 3.0)
        self.assertEqual(without_cancellations, 2.0)

    def test_all_methods_exclude_cancellations_consistently(self):
        """Test that all calculation methods exclude cancellations."""
        items = InvoiceItem.objects.filter(invoice__client=self.client)

        # Method 1: Direct count_sessions
        direct = count_sessions(items, exclude_cancellations=True)

        # Method 2: Chart helpers
        monthly = aggregate_invoice_items_by_month(items, exclude_cancellations=True)
        chart_total = sum(monthly.values())

        # Method 3: Capacity helpers
        capacity = _get_booked_hours(date(2025, 6, 1), date(2025, 6, 30))

        # All should exclude the cancellation
        self.assertEqual(direct, 2.0)
        self.assertEqual(chart_total, 2.0)
        self.assertEqual(capacity, 2.0)
