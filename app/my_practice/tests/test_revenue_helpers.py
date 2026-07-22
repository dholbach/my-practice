"""
Tests for revenue_helpers utility functions.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from my_practice.models import Client, Invoice, Practice
from my_practice.utils.revenue_helpers import RevenueCalculator


class RevenueCalculatorTests(TestCase):
    """Tests for the RevenueCalculator class."""

    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="revenue_helpers-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Create test client
        self.client = Client.objects.create(
            client_code="TEST",
            full_name="Test Client",
            email="test@example.com",
            hourly_rate_60=Decimal("100.00"),
            hourly_rate_90=Decimal("150.00"),
            practice=self.practice,
        )

        # Create invoices with different statuses and years
        self.invoice_paid_2025 = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-1",
            invoice_date=date(2025, 3, 15),
            paid_date=date(2025, 3, 20),
            total=Decimal("200.00"),
            status="paid",
            practice=self.practice,
        )

        self.invoice_paid_2024 = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-2",
            invoice_date=date(2024, 6, 10),
            paid_date=date(2024, 6, 15),
            total=Decimal("300.00"),
            status="paid",
            practice=self.practice,
        )

        self.invoice_sent = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-3",
            invoice_date=date(2025, 4, 1),
            total=Decimal("150.00"),
            status="sent",
            practice=self.practice,
        )

        self.invoice_draft = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-4",
            invoice_date=date(2025, 5, 1),
            total=Decimal("100.00"),
            status="draft",
            practice=self.practice,
        )

        self.invoice_cancelled = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-5",
            invoice_date=date(2025, 6, 1),
            total=Decimal("50.00"),
            status="cancelled",
            practice=self.practice,
        )

    def test_get_total_revenue_no_filters(self):
        """Test total revenue across all paid invoices."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        result = RevenueCalculator.get_total_revenue()
        # Only paid invoices: 200 + 300 = 500
        self.assertEqual(result, Decimal("500.00"))

    def test_get_total_revenue_with_year_filter(self):
        """Test total revenue filtered by year."""
        result = RevenueCalculator.get_total_revenue({"paid_date__year": 2025})
        # Only 2025 paid invoice: 200
        self.assertEqual(result, Decimal("200.00"))

    def test_get_total_revenue_with_client_filter(self):
        """Test total revenue filtered by client."""
        result = RevenueCalculator.get_total_revenue({"client": self.client})
        # All paid invoices for this client: 500
        self.assertEqual(result, Decimal("500.00"))

    def test_get_revenue_stats_basic(self):
        """Test basic revenue statistics."""
        result = RevenueCalculator.get_revenue_stats()

        self.assertEqual(result["total"], Decimal("500.00"))
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["avg"], Decimal("250.00"))

    def test_get_revenue_stats_with_filters(self):
        """Test revenue statistics with filters."""
        result = RevenueCalculator.get_revenue_stats({"paid_date__year": 2024})

        self.assertEqual(result["total"], Decimal("300.00"))
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["avg"], Decimal("300.00"))

    def test_get_revenue_stats_without_avg(self):
        """Test revenue statistics without average."""
        result = RevenueCalculator.get_revenue_stats(include_avg=False)

        self.assertEqual(result["total"], Decimal("500.00"))
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["avg"], Decimal("0"))

    def test_get_year_revenue_with_paid_date(self):
        """Test year revenue using paid_date."""
        result = RevenueCalculator.get_year_revenue(2025, use_paid_date=True)

        self.assertEqual(result["total"], Decimal("200.00"))
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["avg"], Decimal("200.00"))

    def test_get_year_revenue_with_invoice_date(self):
        """Test year revenue using invoice_date."""
        result = RevenueCalculator.get_year_revenue(2025, use_paid_date=False)

        # Using invoice_date: TEST-1 (200) is from 2025
        self.assertEqual(result["total"], Decimal("200.00"))
        self.assertEqual(result["count"], 1)

    def test_get_year_revenue_null_paid_date(self):
        """Test year revenue with null paid_date falls back to invoice_date."""
        # Create invoice with null paid_date
        Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-6",
            invoice_date=date(2025, 7, 1),
            paid_date=None,
            total=Decimal("400.00"),
            status="paid",
            practice=self.practice,
        )

        result = RevenueCalculator.get_year_revenue(2025, use_paid_date=True)

        # Should include both: TEST-1 (200) + TEST-6 (400) = 600
        self.assertEqual(result["total"], Decimal("600.00"))
        self.assertEqual(result["count"], 2)

    def test_get_month_revenue(self):
        """Test monthly revenue calculation."""
        result = RevenueCalculator.get_month_revenue(2025, 3)

        # March 2025: TEST-1 (200)
        self.assertEqual(result["total"], Decimal("200.00"))
        self.assertEqual(result["count"], 1)

    def test_get_month_revenue_empty(self):
        """Test monthly revenue for month with no invoices."""
        result = RevenueCalculator.get_month_revenue(2025, 12)

        self.assertEqual(result["total"], Decimal("0"))
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["avg"], Decimal("0"))

    def test_get_client_revenue_paid_only(self):
        """Test client revenue (paid invoices only)."""
        result = RevenueCalculator.get_client_revenue(self.client)

        self.assertEqual(result["total"], Decimal("500.00"))
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["avg"], Decimal("250.00"))

    def test_get_client_revenue_include_unpaid(self):
        """Test client revenue including all statuses."""
        result = RevenueCalculator.get_client_revenue(self.client, include_unpaid=True)

        # All invoices: 200 + 300 + 150 + 100 + 50 = 800
        self.assertEqual(result["total"], Decimal("800.00"))
        self.assertEqual(result["count"], 5)

    def test_get_status_breakdown(self):
        """Test status breakdown for all invoices."""
        result = RevenueCalculator.get_status_breakdown()

        # Paid
        self.assertEqual(result["paid"]["count"], 2)
        self.assertEqual(result["paid"]["total"], Decimal("500.00"))

        # Sent
        self.assertEqual(result["sent"]["count"], 1)
        self.assertEqual(result["sent"]["total"], Decimal("150.00"))

        # Draft
        self.assertEqual(result["draft"]["count"], 1)
        self.assertEqual(result["draft"]["total"], Decimal("100.00"))

        # Cancelled
        self.assertEqual(result["cancelled"]["count"], 1)
        self.assertEqual(result["cancelled"]["total"], Decimal("50.00"))

    def test_get_status_breakdown_with_filters(self):
        """Test status breakdown filtered by year."""
        result = RevenueCalculator.get_status_breakdown({"invoice_date__year": 2025})

        # 2025 invoices only
        self.assertEqual(result["paid"]["count"], 1)  # TEST-1
        self.assertEqual(result["paid"]["total"], Decimal("200.00"))

        self.assertEqual(result["sent"]["count"], 1)  # TEST-3
        self.assertEqual(result["sent"]["total"], Decimal("150.00"))

    def test_get_status_breakdown_empty(self):
        """Test status breakdown when no invoices match."""
        result = RevenueCalculator.get_status_breakdown({"invoice_date__year": 2020})

        self.assertEqual(result["paid"]["count"], 0)
        self.assertEqual(result["paid"]["total"], Decimal("0"))
        self.assertEqual(result["sent"]["count"], 0)
        self.assertEqual(result["draft"]["count"], 0)
        self.assertEqual(result["cancelled"]["count"], 0)

    def test_get_status_breakdown_with_year_param_uses_paid_date(self):
        """Test status breakdown with year param filters paid by paid_date."""
        # Create invoice sent in 2025 but paid in 2030 (future year unlikely to have data)
        invoice_paid_2030 = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-CROSS-YEAR",
            invoice_date=date(2029, 12, 15),  # Created in 2029
            paid_date=date(2030, 1, 5),  # Paid in 2030
            total=Decimal("400.00"),
            status="paid",
            practice=self.practice,
        )

        # Using year=2030 should find invoices PAID in 2030
        result = RevenueCalculator.get_status_breakdown(year=2030)

        # Should find the cross-year paid invoice (by paid_date)
        self.assertEqual(result["paid"]["count"], 1)
        self.assertEqual(result["paid"]["total"], Decimal("400.00"))

        # No drafts/sent/cancelled with invoice_date in 2030
        self.assertEqual(result["draft"]["count"], 0)
        self.assertEqual(result["sent"]["count"], 0)
        self.assertEqual(result["cancelled"]["count"], 0)

        # Using year=2025 should NOT include that invoice in paid
        result_2025 = RevenueCalculator.get_status_breakdown(year=2025)

        # Paid invoices where paid_date is in 2025 (TEST-1 only)
        self.assertEqual(result_2025["paid"]["count"], 1)
        self.assertEqual(result_2025["paid"]["total"], Decimal("200.00"))

        # Clean up
        invoice_paid_2030.delete()

    def test_get_paid_revenue_for_range_basic(self):
        """Test paid revenue for a date range covering only the 2025 paid invoice."""
        total = RevenueCalculator.get_paid_revenue_for_range(date(2025, 1, 1), date(2025, 12, 31))
        self.assertEqual(total, Decimal("200.00"))

    def test_get_paid_revenue_for_range_null_paid_date_fallback(self):
        """Range should include invoices with null paid_date via invoice_date fallback."""
        Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-RANGE-NULL",
            invoice_date=date(2025, 7, 1),
            paid_date=None,
            total=Decimal("400.00"),
            status="paid",
            practice=self.practice,
        )

        total = RevenueCalculator.get_paid_revenue_for_range(date(2025, 1, 1), date(2025, 12, 31))

        # TEST-1 (200, paid_date in range) + TEST-RANGE-NULL (400, invoice_date fallback)
        self.assertEqual(total, Decimal("600.00"))

    def test_get_paid_revenue_for_range_scoped_by_practice(self):
        """Passing a practice should exclude paid invoices from other practices."""
        other_practice = Practice.objects.create(
            name="Other Practice",
            slug="revenue_helpers-2",
            title="Other Practitioner",
            email="other@practice.com",
            city="Hamburg",
        )
        other_client = Client.objects.create(
            client_code="OTHERP",
            full_name="Other Practice Client",
            email="otherp@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=other_practice,
        )
        Invoice.objects.create(
            client=other_client,
            invoice_number="OTHERP-1",
            invoice_date=date(2025, 3, 10),
            paid_date=date(2025, 3, 12),
            total=Decimal("999.00"),
            status="paid",
            practice=other_practice,
        )

        total = RevenueCalculator.get_paid_revenue_for_range(
            date(2025, 1, 1), date(2025, 12, 31), practice=self.practice
        )

        # Only TEST-1 (200) from self.practice, not OTHERP-1 (999) from other_practice
        self.assertEqual(total, Decimal("200.00"))

    def test_get_paid_revenue_for_range_no_matches(self):
        """Range with no matching invoices should return Decimal('0'), not None."""
        total = RevenueCalculator.get_paid_revenue_for_range(date(2020, 1, 1), date(2020, 12, 31))
        self.assertEqual(total, Decimal("0"))

    def test_no_invoices(self):
        """Test calculations when no invoices exist."""
        # Delete all invoices
        Invoice.objects.all().delete()

        total = RevenueCalculator.get_total_revenue()
        self.assertEqual(total, Decimal("0"))

        stats = RevenueCalculator.get_revenue_stats()
        self.assertEqual(stats["total"], Decimal("0"))
        self.assertEqual(stats["count"], 0)
        self.assertEqual(stats["avg"], Decimal("0"))

    def test_multiple_clients(self):
        """Test that client filtering works correctly."""
        # Create another client with invoices
        client2 = Client.objects.create(
            client_code="OTHER",
            full_name="Other Client",
            email="other@example.com",
            hourly_rate_60=Decimal("80.00"),
            practice=self.practice,
        )

        Invoice.objects.create(
            client=client2,
            invoice_number="OTHER-1",
            invoice_date=date(2025, 1, 1),
            total=Decimal("500.00"),
            status="paid",
            practice=self.practice,
        )

        # Test client-specific revenue
        result1 = RevenueCalculator.get_client_revenue(self.client)
        result2 = RevenueCalculator.get_client_revenue(client2)

        self.assertEqual(result1["total"], Decimal("500.00"))
        self.assertEqual(result2["total"], Decimal("500.00"))

        # Total revenue should be sum of both
        total = RevenueCalculator.get_total_revenue()
        self.assertEqual(total, Decimal("1000.00"))


class ApplyYearFilterTests(TestCase):
    """Tests for the apply_year_filter method."""

    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="revenue_helpers-2",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.client = Client.objects.create(
            client_code="TEST",
            full_name="Test Client",
            email="test@example.com",
            hourly_rate_60=Decimal("100.00"),
            practice=self.practice,
        )

        # Invoice created in 2025, paid in 2026
        self.invoice_cross_year = Invoice.objects.create(
            client=self.client,
            invoice_number="CROSS-1",
            invoice_date=date(2025, 12, 15),
            paid_date=date(2026, 1, 5),
            total=Decimal("300.00"),
            status="paid",
            practice=self.practice,
        )

        # Invoice created and paid in 2025
        self.invoice_2025 = Invoice.objects.create(
            client=self.client,
            invoice_number="IN-2025",
            invoice_date=date(2025, 6, 1),
            paid_date=date(2025, 6, 15),
            total=Decimal("200.00"),
            status="paid",
            practice=self.practice,
        )

        # Draft invoice in 2026
        self.invoice_draft_2026 = Invoice.objects.create(
            client=self.client,
            invoice_number="DRAFT-2026",
            invoice_date=date(2026, 1, 10),
            total=Decimal("150.00"),
            status="draft",
            practice=self.practice,
        )

    def test_apply_year_filter_paid_status_uses_paid_date(self):
        """Test that paid invoices are filtered by paid_date."""
        qs = Invoice.objects.filter(status="paid")
        result = RevenueCalculator.apply_year_filter(qs, 2026, status_filter="paid")

        # Should find CROSS-1 (paid in 2026), not IN-2025
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().invoice_number, "CROSS-1")

    def test_apply_year_filter_draft_status_uses_invoice_date(self):
        """Test that draft invoices are filtered by invoice_date."""
        qs = Invoice.objects.filter(status="draft")
        result = RevenueCalculator.apply_year_filter(qs, 2026, status_filter="draft")

        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().invoice_number, "DRAFT-2026")

    def test_apply_year_filter_mixed_uses_q_objects(self):
        """Test mixed filtering without specific status."""
        qs = Invoice.objects.all()
        result = RevenueCalculator.apply_year_filter(qs, 2026, status_filter=None)

        # Should find: CROSS-1 (paid_date in 2026), DRAFT-2026 (invoice_date in 2026)
        self.assertEqual(result.count(), 2)
        numbers = set(result.values_list("invoice_number", flat=True))
        self.assertEqual(numbers, {"CROSS-1", "DRAFT-2026"})


class RevenueSubqueryTests(TestCase):
    """Tests for centralized subquery methods."""

    def setUp(self):
        """Set up test data with items."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="revenue_helpers-3",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        from my_practice.models import InvoiceItem, ServiceType, Session

        # Create test client
        self.client = Client.objects.create(
            client_code="TST",
            full_name="Test Client",
            email="test@example.com",
            hourly_rate_60=Decimal("80.00"),
            practice=self.practice,
        )

        # Create service type
        self.service = ServiceType.objects.create(
            code="test_60",
            name="Test Session",
            default_duration=60,
            practice=self.practice,
        )

        self.cancel_service = ServiceType.objects.create(
            code="cancel_fee",
            name="Cancellation Fee",
            default_duration=60,
            practice=self.practice,
        )

        # Create paid invoice with items
        self.paid_invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TST-1",
            invoice_date=date(2025, 1, 1),
            paid_date=date(2025, 1, 5),
            total=Decimal("240.00"),
            status="paid",
            practice=self.practice,
        )

        InvoiceItem.objects.create(
            invoice=self.paid_invoice,
            service_type=self.service,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2025, 1, 1),
                duration=60,
            ),
            rate=Decimal("80.00"),
            quantity=Decimal("1.00"),
        )

        InvoiceItem.objects.create(
            invoice=self.paid_invoice,
            service_type=self.service,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2025, 1, 2),
                duration=60,
            ),
            rate=Decimal("80.00"),
            quantity=Decimal("1.00"),
        )

        InvoiceItem.objects.create(
            invoice=self.paid_invoice,
            service_type=self.cancel_service,
            session=Session.objects.create(
                client=self.client,
                session_date=date(2025, 1, 3),
                duration=60,
            ),
            rate=Decimal("80.00"),
            quantity=Decimal("1.00"),
        )

    def test_get_client_revenue_subquery(self):
        """Test centralized revenue subquery."""
        result = Client.objects.annotate(
            total_revenue=RevenueCalculator.get_client_revenue_subquery()
        ).get(client_code="TST")

        self.assertEqual(result.total_revenue, Decimal("240.00"))

    def test_get_client_sessions_subquery_excludes_cancellations(self):
        """Test session subquery excludes cancellations by default."""
        result = Client.objects.annotate(
            total_sessions=RevenueCalculator.get_client_sessions_subquery()
        ).get(client_code="TST")

        # Should be 2 (excluding the "Ausfall" item)
        self.assertEqual(result.total_sessions, Decimal("2.00"))

    def test_get_client_sessions_subquery_includes_cancellations(self):
        """Test session subquery can include cancellations."""
        result = Client.objects.annotate(
            total_sessions=RevenueCalculator.get_client_sessions_subquery(
                exclude_cancellations=False
            )
        ).get(client_code="TST")

        # Should be 3 (including the "Ausfall" item)
        self.assertEqual(result.total_sessions, Decimal("3.00"))

    def test_subqueries_together_no_multiplication(self):
        """Test that using both subqueries together doesn't cause JOIN multiplication."""
        result = Client.objects.annotate(
            total_revenue=RevenueCalculator.get_client_revenue_subquery(),
            total_sessions=RevenueCalculator.get_client_sessions_subquery(),
        ).get(client_code="TST")

        # Revenue should be correct (not multiplied by item count)
        self.assertEqual(result.total_revenue, Decimal("240.00"))
        self.assertEqual(result.total_sessions, Decimal("2.00"))

    def test_subqueries_with_no_data(self):
        """Test subqueries return None for clients with no invoices."""
        # Create client with no invoices
        Client.objects.create(
            client_code="EMPTY",
            full_name="Empty Client",
            email="empty@example.com",
            practice=self.practice,
        )

        result = Client.objects.annotate(
            total_revenue=RevenueCalculator.get_client_revenue_subquery(),
            total_sessions=RevenueCalculator.get_client_sessions_subquery(),
        ).get(client_code="EMPTY")

        self.assertIsNone(result.total_revenue)
        self.assertIsNone(result.total_sessions)
