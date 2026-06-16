"""
Tests for Analytics Dashboard Time Period Filtering
"""

from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import (
    Client,
    CompanyExpense,
    Invoice,
    InvoiceItem,
    Practice,
    ServiceType,
    Session,
)


class AnalyticsTimeFilterTest(TestCase):
    """Test analytics dashboard time period filter functionality"""

    def setUp(self):
        """Set up test data"""
        self.client_http = TestClient()
        self.url = reverse("analytics")

        # Create practice (uses defaults)
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="analytics-time-filter-fix",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Create client and service type
        self.client_obj = Client.objects.create(
            client_code="TC1",
            full_name="Test Client",
            email="test@example.com",
            hourly_rate_60=Decimal("120.00"),
            hourly_rate_90=Decimal("180.00"),
            practice=self.practice,
        )

        self.service_type = ServiceType.objects.create(
            code="therapy_60",
            name="Therapy Session 60min",
            name_de="Psychotherapie, 60 Min.",
            practice=self.practice,
        )

        # Create invoices across different time periods
        today = date.today()

        # Last month
        last_month = today - relativedelta(months=1)
        self.invoice_last_month = Invoice.objects.create(
            client=self.client_obj,
            invoice_number="INV-MONTH-001",
            invoice_date=last_month,
            paid_date=last_month,
            status="paid",
            practice=self.practice,
        )
        InvoiceItem.objects.create(
            invoice=self.invoice_last_month,
            service_type=self.service_type,
            quantity=1,
            rate=Decimal("120.00"),
            session=Session.objects.create(
                client=self.client_obj,
                session_date=last_month,
                duration=60,
            ),
        )

        # Last quarter (2 months ago)
        last_quarter = today - relativedelta(months=2)
        self.invoice_last_quarter = Invoice.objects.create(
            client=self.client_obj,
            invoice_number="INV-QUARTER-001",
            invoice_date=last_quarter,
            paid_date=last_quarter,
            status="paid",
            practice=self.practice,
        )
        InvoiceItem.objects.create(
            invoice=self.invoice_last_quarter,
            service_type=self.service_type,
            quantity=2,
            rate=Decimal("120.00"),
            session=Session.objects.create(
                client=self.client_obj,
                session_date=last_quarter,
                duration=60,
            ),
        )

        # Last year (13 months ago)
        last_year = today - relativedelta(months=13)
        self.invoice_last_year = Invoice.objects.create(
            client=self.client_obj,
            invoice_number="INV-YEAR-001",
            invoice_date=last_year,
            paid_date=last_year,
            status="paid",
            practice=self.practice,
        )
        InvoiceItem.objects.create(
            invoice=self.invoice_last_year,
            service_type=self.service_type,
            quantity=3,
            rate=Decimal("120.00"),
            session=Session.objects.create(
                client=self.client_obj,
                session_date=last_year,
                duration=60,
            ),
        )

        # Old invoice (3 years ago)
        three_years_ago = today - relativedelta(years=3)
        self.invoice_old = Invoice.objects.create(
            client=self.client_obj,
            invoice_number="INV-OLD-001",
            invoice_date=three_years_ago,
            paid_date=three_years_ago,
            status="paid",
            practice=self.practice,
        )
        InvoiceItem.objects.create(
            invoice=self.invoice_old,
            service_type=self.service_type,
            quantity=4,
            rate=Decimal("120.00"),
            session=Session.objects.create(
                client=self.client_obj,
                session_date=three_years_ago,
                duration=60,
            ),
        )

        # Create expenses
        CompanyExpense.objects.create(
            description="Expense Last Month",
            amount=Decimal("50.00"),
            category="miete",
            date=last_month,
            is_tax_deductible=True,
            has_invoice=True,
            practice=self.practice,
        )

        CompanyExpense.objects.create(
            description="Expense Old",
            amount=Decimal("100.00"),
            category="software",
            date=three_years_ago,
            is_tax_deductible=True,
            has_invoice=True,
            practice=self.practice,
        )

    def test_default_filter_shows_all_time(self):
        """Test default view shows all-time data"""
        response = self.client_http.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_period"], "all")

        # Should include all invoices
        revenue_trends = response.context["revenue_trends"]
        self.assertIsNotNone(revenue_trends)

    def test_month_filter(self):
        """Test last month filter"""
        response = self.client_http.get(self.url, {"period": "month"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_period"], "month")

        # Should only include last month's data
        profit_data = response.context["profit_data"]
        # Month filter should show limited data
        self.assertIsNotNone(profit_data)

    def test_quarter_filter(self):
        """Test last quarter filter"""
        response = self.client_http.get(self.url, {"period": "quarter"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_period"], "quarter")

    def test_year_filter(self):
        """Test last year filter"""
        response = self.client_http.get(self.url, {"period": "year"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_period"], "year")

    def test_custom_date_range(self):
        """Test custom date range filter"""
        today = date.today()
        start = (today - relativedelta(months=6)).isoformat()
        end = today.isoformat()

        response = self.client_http.get(
            self.url, {"period": "custom", "start_date": start, "end_date": end}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_period"], "custom")
        self.assertEqual(response.context["start_date"], start)
        self.assertEqual(response.context["end_date"], end)

    def test_invalid_custom_dates_fallback(self):
        """Test invalid custom dates fall back to all-time"""
        response = self.client_http.get(
            self.url,
            {"period": "custom", "start_date": "invalid", "end_date": "2024-01-01"},
        )
        self.assertEqual(response.status_code, 200)
        # Should fall back to "all"
        self.assertEqual(response.context["selected_period"], "all")

    def test_ui_shows_filter_controls(self):
        """Test UI displays filter controls"""
        response = self.client_http.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="period"')
        self.assertContains(response, "Zeitraum")
        self.assertContains(response, "Alle Jahre (")
        self.assertContains(response, "-heute)")
        self.assertContains(response, "Letztes Jahr")
        self.assertContains(response, "Letzter Monat")

    def test_filter_persistence(self):
        """Test that filter parameters are included in context"""
        response = self.client_http.get(self.url, {"period": "quarter"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("selected_period", response.context)
        self.assertEqual(response.context["selected_period"], "quarter")

    def test_reset_link_present(self):
        """Test reset link appears when filter is active"""
        response = self.client_http.get(self.url, {"period": "month"})
        self.assertEqual(response.status_code, 200)
        # When period != 'all', reset link should be present
        self.assertContains(response, "Zurücksetzen")
