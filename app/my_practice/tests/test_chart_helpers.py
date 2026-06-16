"""
Tests for chart_helpers utility functions.
"""

from datetime import date

from django.test import TestCase
from my_practice.models import Client, Invoice, InvoiceItem, Practice, ServiceType, Session
from my_practice.utils.chart_helpers import (
    aggregate_invoice_items_by_month,
    format_month_key,
    format_month_label,
    prepare_monthly_chart_data,
)


class FormatMonthKeyTests(TestCase):
    """Tests for format_month_key() function."""

    def test_format_month_key_basic(self):
        """Test basic month key formatting."""
        test_date = date(2025, 12, 15)
        result = format_month_key(test_date)
        self.assertEqual(result, "2025-12")

    def test_format_month_key_january(self):
        """Test formatting January (single digit month)."""
        test_date = date(2025, 1, 1)
        result = format_month_key(test_date)
        self.assertEqual(result, "2025-01")

    def test_format_month_key_october(self):
        """Test formatting October (double digit month)."""
        test_date = date(2023, 10, 31)
        result = format_month_key(test_date)
        self.assertEqual(result, "2023-10")


class FormatMonthLabelTests(TestCase):
    """Tests for format_month_label() function."""

    def test_format_month_label_short(self):
        """Test short format (mm/yy)."""
        result = format_month_label("2025-12", "short")
        self.assertEqual(result, "12/25")

    def test_format_month_label_medium(self):
        """Test medium format (Mon YYYY)."""
        result = format_month_label("2025-12", "medium")
        self.assertEqual(result, "Dec 2025")

    def test_format_month_label_long(self):
        """Test long format (Month YYYY)."""
        result = format_month_label("2025-12", "long")
        self.assertEqual(result, "December 2025")

    def test_format_month_label_default(self):
        """Test default format (should be short)."""
        result = format_month_label("2025-12")
        self.assertEqual(result, "12/25")

    def test_format_month_label_invalid_format(self):
        """Test with invalid format_type (should default to short)."""
        result = format_month_label("2025-12", "invalid")
        self.assertEqual(result, "12/25")


class AggregateInvoiceItemsByMonthTests(TestCase):
    """Tests for aggregate_invoice_items_by_month() function."""

    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="chart_helpers-1",
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
        self.cancel_service_type = ServiceType.objects.create(
            code="cancel_fee",
            name="Cancellation Fee",
            practice=self.practice,
        )
        self.client = Client.objects.create(
            client_code="TEST01", full_name="Test Client", practice=self.practice
        )
        self.invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="2025-001",
            invoice_date=date(2025, 1, 15),
            total=150.00,
            status="paid",
            practice=self.practice,
        )

    def test_aggregate_basic(self):
        """Test basic aggregation by month."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Create items in different months
        s1 = Session.objects.create(client=self.client, session_date=date(2025, 1, 15), duration=60)
        s2 = Session.objects.create(client=self.client, session_date=date(2025, 1, 22), duration=60)
        s3 = Session.objects.create(client=self.client, session_date=date(2025, 2, 5), duration=90)
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=s1,
            quantity=1,
            rate=75.00,
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=s2,
            quantity=1,
            rate=75.00,
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=s3,
            quantity=1,
            rate=112.50,
        )

        items = InvoiceItem.objects.all()
        result = aggregate_invoice_items_by_month(items)

        self.assertIn("2025-01", result)
        self.assertIn("2025-02", result)
        self.assertEqual(result["2025-01"], 2.0)  # 2 hours
        self.assertEqual(result["2025-02"], 1.5)  # 1.5 hours

    def test_aggregate_exclude_cancellations(self):
        """Test that cancellations are excluded."""
        s1 = Session.objects.create(client=self.client, session_date=date(2025, 1, 15), duration=60)
        s2 = Session.objects.create(client=self.client, session_date=date(2025, 1, 22), duration=60)
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=s1,
            quantity=1,
            rate=75.00,
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.cancel_service_type,
            session=s2,
            quantity=1,
            rate=37.50,
        )

        items = InvoiceItem.objects.all()
        result = aggregate_invoice_items_by_month(items, exclude_cancellations=True)

        self.assertEqual(result["2025-01"], 1.0)  # Only one session counted

    def test_aggregate_include_cancellations(self):
        """Test that cancellations are included when specified."""
        s1 = Session.objects.create(client=self.client, session_date=date(2025, 1, 15), duration=60)
        s2 = Session.objects.create(client=self.client, session_date=date(2025, 1, 22), duration=60)
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=s1,
            quantity=1,
            rate=75.00,
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.cancel_service_type,
            session=s2,
            quantity=1,
            rate=37.50,
        )

        items = InvoiceItem.objects.all()
        result = aggregate_invoice_items_by_month(items, exclude_cancellations=False)

        self.assertEqual(result["2025-01"], 2.0)  # Both counted

    def test_aggregate_no_session_date(self):
        """Test that items are indexed by their session's date."""
        s1 = Session.objects.create(client=self.client, session_date=date(2025, 1, 15), duration=60)
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=s1,
            quantity=1,
            rate=75.00,
        )

        items = InvoiceItem.objects.all()
        result = aggregate_invoice_items_by_month(items)

        # Should have one month with data
        self.assertEqual(len(result), 1)
        self.assertIn("2025-01", result)

    def test_aggregate_multiple_quantities(self):
        """Test items with quantity > 1."""
        s1 = Session.objects.create(client=self.client, session_date=date(2025, 1, 15), duration=60)
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=s1,
            quantity=3,  # Multiple sessions
            rate=75.00,
        )

        items = InvoiceItem.objects.all()
        result = aggregate_invoice_items_by_month(items)

        self.assertEqual(result["2025-01"], 3.0)  # 3 hours


class PrepareMonthlyChartDataTests(TestCase):
    """Tests for prepare_monthly_chart_data() function."""

    def test_prepare_basic(self):
        """Test basic chart data preparation."""
        monthly_data = {
            "2025-01": 6.0,
            "2025-02": 4.5,
            "2025-03": 7.5,
        }

        result = prepare_monthly_chart_data(monthly_data, value_key="hours")

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], {"month": "01/25", "hours": 6.0})
        self.assertEqual(result[1], {"month": "02/25", "hours": 4.5})
        self.assertEqual(result[2], {"month": "03/25", "hours": 7.5})

    def test_prepare_sorts_chronologically(self):
        """Test that months are sorted chronologically."""
        monthly_data = {
            "2025-03": 7.5,
            "2025-01": 6.0,
            "2025-02": 4.5,
        }

        result = prepare_monthly_chart_data(monthly_data)

        self.assertEqual(result[0]["month"], "01/25")
        self.assertEqual(result[1]["month"], "02/25")
        self.assertEqual(result[2]["month"], "03/25")

    def test_prepare_custom_value_key(self):
        """Test with custom value key."""
        monthly_data = {"2025-01": 1500.0}

        result = prepare_monthly_chart_data(monthly_data, value_key="revenue")

        self.assertEqual(result[0]["revenue"], 1500.0)
        self.assertNotIn("value", result[0])

    def test_prepare_short_format(self):
        """Test short label format."""
        monthly_data = {"2025-12": 5.0}

        result = prepare_monthly_chart_data(monthly_data, label_format="short")

        self.assertEqual(result[0]["month"], "12/25")

    def test_prepare_medium_format(self):
        """Test medium label format."""
        monthly_data = {"2025-12": 5.0}

        result = prepare_monthly_chart_data(monthly_data, label_format="medium")

        self.assertEqual(result[0]["month"], "Dec 2025")

    def test_prepare_long_format(self):
        """Test long label format."""
        monthly_data = {"2025-12": 5.0}

        result = prepare_monthly_chart_data(monthly_data, label_format="long")

        self.assertEqual(result[0]["month"], "December 2025")

    def test_prepare_empty_data(self):
        """Test with empty data."""
        monthly_data = {}

        result = prepare_monthly_chart_data(monthly_data)

        self.assertEqual(len(result), 0)
        self.assertEqual(result, [])

    def test_prepare_single_month(self):
        """Test with single month."""
        monthly_data = {"2025-06": 10.5}

        result = prepare_monthly_chart_data(monthly_data, value_key="hours")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], {"month": "06/25", "hours": 10.5})
