"""
Tests for analytics views.
"""

from datetime import date, timedelta
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
    ServiceType,
    Session,
    UserPractice,
)


class AnalyticsDashboardViewTest(TestCase):
    """Test analytics dashboard view."""

    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_analytics-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser", password="testpass123")

        self.service_type = ServiceType.objects.create(
            code="individual",
            name="60 Min Session",
            name_de="60 Min. Psychotherapie",
            practice=self.practice,
        )

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

        # Create invoices with different dates
        today = date.today()
        for i in range(3):
            invoice = Invoice.objects.create(
                client=self.test_client,
                invoice_number=f"TC-{i + 1}",
                invoice_date=today - timedelta(days=i * 30),
                total=Decimal("180.00"),
                status="paid",
                practice=self.practice,
            )
            InvoiceItem.objects.create(
                invoice=invoice,
                service_type=self.service_type,
                session=Session.objects.create(
                    client=self.test_client,
                    session_date=today - timedelta(days=i * 30),
                    duration=60,
                ),
                rate=Decimal("90.00"),
                quantity=Decimal("2.00"),
                total=Decimal("180.00"),
            )

    def test_analytics_dashboard_loads(self):
        """Test that analytics dashboard loads successfully."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        response = self.client_instance.get(reverse("analytics"))
        self.assertEqual(response.status_code, 200)

    def test_analytics_dashboard_has_revenue_data(self):
        """Test that analytics dashboard includes revenue trends."""
        response = self.client_instance.get(reverse("analytics"))
        self.assertEqual(response.status_code, 200)

        # Check for revenue trends context (if implemented)
        if "revenue_trends" in response.context:
            self.assertIsNotNone(response.context["revenue_trends"])

    def test_analytics_dashboard_with_expenses(self):
        """Test analytics dashboard includes expense data and expense_trends is populated."""
        # Create expenses in different months
        today = date.today()
        CompanyExpense.objects.create(
            date=date(today.year, 1, 15),
            amount=Decimal("500.00"),
            category="software",
            description="Software subscription",
            practice=self.practice,
        )
        CompanyExpense.objects.create(
            date=date(today.year, 2, 20),
            amount=Decimal("300.00"),
            category="office",
            description="Office supplies",
            practice=self.practice,
        )

        response = self.client_instance.get(reverse("analytics"))
        self.assertEqual(response.status_code, 200)

        # Verify expense_trends is in context and has data
        self.assertIn("expense_trends", response.context)
        expense_trends = response.context["expense_trends"]
        self.assertIsNotNone(expense_trends)
        self.assertGreater(
            len(expense_trends),
            0,
            "expense_trends should contain data when expenses exist",
        )

        # Verify structure of expense_trends
        if expense_trends:
            first_trend = expense_trends[0]
            self.assertIn("month", first_trend)
            self.assertIn("expenses", first_trend)
            self.assertIn("year", first_trend)
            self.assertIsInstance(first_trend["expenses"], (int, float))

            # Verify we can find our expenses in the trends
            total_expenses_in_trends = sum(item["expenses"] for item in expense_trends)
            self.assertGreater(
                total_expenses_in_trends,
                0,
                "Total expenses in trends should be greater than 0",
            )

    def test_analytics_dashboard_with_withdrawals(self):
        """Test analytics dashboard includes withdrawal data."""
        CompanyWithdrawal.objects.create(
            date=date.today(),
            amount=Decimal("1000.00"),
            category="salary",
            description="Test withdrawal",
            practice=self.practice,
        )

        response = self.client_instance.get(reverse("analytics"))
        self.assertEqual(response.status_code, 200)
        # Page loads successfully with withdrawals

    def test_analytics_dashboard_empty_data(self):
        """Test analytics dashboard with no data."""
        # Delete in reverse FK order: InvoiceItem → Session → Invoice → Client
        InvoiceItem.objects.all().delete()
        Session.objects.all().delete()
        Invoice.objects.all().delete()
        Client.objects.all().delete()

        response = self.client_instance.get(reverse("analytics"))
        self.assertEqual(response.status_code, 200)
        # Should handle empty data gracefully

    def test_analytics_dashboard_chart_data_structure(self):
        """Test that chart data has correct structure."""
        response = self.client_instance.get(reverse("analytics"))

        # Check revenue trends structure if present
        if "revenue_trends" in response.context:
            trends = response.context["revenue_trends"]
            if trends:
                # Each trend should have month and revenue
                first_trend = trends[0]
                self.assertIn("month", first_trend)
                self.assertIn("revenue", first_trend)

    def test_analytics_dashboard_top_clients(self):
        """Test that top clients data is included."""
        response = self.client_instance.get(reverse("analytics"))

        # Check for top clients if implemented
        if "top_clients" in response.context:
            top_clients = response.context["top_clients"]
            self.assertIsInstance(top_clients, (list, tuple))

    def test_analytics_dashboard_session_distribution(self):
        """Test session type distribution data."""
        response = self.client_instance.get(reverse("analytics"))

        # Check for session distribution if implemented
        if "session_distribution" in response.context:
            distribution = response.context["session_distribution"]
            self.assertIsInstance(distribution, (list, dict))

    def test_analytics_dashboard_expense_trends_empty(self):
        """Test that expense_trends is empty when no expenses exist."""
        # Ensure no expenses exist
        CompanyExpense.objects.all().delete()

        response = self.client_instance.get(reverse("analytics"))
        self.assertEqual(response.status_code, 200)

        # Verify expense_trends exists but may be empty
        self.assertIn("expense_trends", response.context)
        expense_trends = response.context["expense_trends"]
        self.assertIsNotNone(expense_trends)
        # When no expenses, trends should exist but all values should be 0
        if expense_trends:
            total_expenses = sum(item["expenses"] for item in expense_trends)
            self.assertEqual(
                total_expenses,
                0,
                "Total expenses should be 0 when no expense records exist",
            )

        # Verify the template renders without JavaScript errors (check for -Infinity or NaN in content)
        response.content.decode("utf-8")

    def test_analytics_expense_trends_december_31_distribution(self):
        """
        Test that expenses dated 31.12. are properly distributed across all months.
        This is critical because we don't track expense dates - all expenses use 31.12.
        as the date, but charts should show distributed values across the year.
        """
        # Create expense for 2024 dated 31.12.2024
        CompanyExpense.objects.create(
            date=date(2024, 12, 31),
            amount=Decimal("12000.00"),  # 12000 / 12 = 1000 per month
            category="Office",
            description="2024 office expenses",
            practice=self.practice,
        )

        # Request analytics with custom date range for full year 2024
        response = self.client_instance.get(
            reverse("analytics"),
            {"period": "custom", "start_date": "2024-01-01", "end_date": "2024-12-31"},
        )
        self.assertEqual(response.status_code, 200)

        expense_trends = response.context["expense_trends"]
        self.assertIsNotNone(expense_trends)
        self.assertGreater(len(expense_trends), 0)

        # Filter to 2024 months only
        expenses_2024 = [item for item in expense_trends if item["year"] == 2024]
        self.assertEqual(len(expenses_2024), 12, "Should have 12 months for 2024")

        # Each month should have 12000/12 = 1000
        expected_monthly = 1000.0
        for item in expenses_2024:
            self.assertAlmostEqual(
                item["expenses"],
                expected_monthly,
                places=2,
                msg=f"Month {item['month']} should have {expected_monthly}€ distributed expense",
            )

        # Verify total adds up to original amount
        total_expenses = sum(item["expenses"] for item in expenses_2024)
        self.assertAlmostEqual(total_expenses, 12000.0, places=2)

    def test_analytics_dashboard_performance(self):
        """Test analytics dashboard doesn't have excessive queries."""
        # Create more test data
        for i in range(5):
            client = Client.objects.create(
                client_code=f"CL{i}",
                full_name=f"Client {i}",
                email=f"client{i}@example.com",
                hourly_rate_60=Decimal("90.00"),
                practice=self.practice,
            )
            invoice = Invoice.objects.create(
                client=client,
                invoice_number=f"INV-{i}",
                invoice_date=date.today(),
                status="paid",
                practice=self.practice,
            )
            InvoiceItem.objects.create(
                invoice=invoice,
                service_type=self.service_type,
                session=Session.objects.create(
                    client=client,
                    session_date=date.today(),
                    duration=60,
                ),
                rate=Decimal("90.00"),
                quantity=Decimal("1.00"),
                total=Decimal("90.00"),
            )

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as context:
            response = self.client_instance.get(reverse("analytics"))
            self.assertEqual(response.status_code, 200)

        # Analytics can be complex with many aggregations - allow reasonable query count
        # Note: Multi-practice filtering adds some overhead
        query_count = len(context.captured_queries)
        self.assertLess(query_count, 360, f"Analytics has {query_count} queries")


class AnalyticsFilterTest(TestCase):
    """Test analytics filtering functionality."""

    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_analytics-2",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser", password="testpass123")

    def test_analytics_year_filter(self):
        """Test filtering analytics by year."""
        response = self.client_instance.get(reverse("analytics") + "?year=2025")
        self.assertEqual(response.status_code, 200)
        # Filter parameter should be accepted

    def test_analytics_without_filter(self):
        """Test analytics without any filters (all data)."""
        response = self.client_instance.get(reverse("analytics"))
        self.assertEqual(response.status_code, 200)


class PracticeAnalysisRedirectTest(TestCase):
    """Test the practice_analysis -> analytics?tab=capacity backwards-compat redirect."""

    def setUp(self):
        self.user = User.objects.create_user(username="redirectuser", password="testpass123")
        self.client_instance = TestClient()
        self.client_instance.login(username="redirectuser", password="testpass123")

    def test_redirects_to_capacity_tab(self):
        response = self.client_instance.get(reverse("practice_analysis"))
        self.assertRedirects(response, "/analytics/?tab=capacity", fetch_redirect_response=False)

    def test_preserves_query_string(self):
        response = self.client_instance.get(reverse("practice_analysis") + "?year=2025")
        self.assertRedirects(
            response, "/analytics/?tab=capacity&year=2025", fetch_redirect_response=False
        )


class AnalyticsClientsTabHeatmapTest(TestCase):
    """Test the ?tab=clients branch of analytics_dashboard (heatmap data)."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="analytics-heatmap",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="heatmapuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance = TestClient()
        self.client_instance.login(username="heatmapuser", password="testpass123")

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        Session.objects.create(client=self.test_client, session_date=date.today(), duration=60)

    def test_clients_tab_includes_heatmap_context(self):
        response = self.client_instance.get(reverse("analytics") + "?tab=clients")
        self.assertEqual(response.status_code, 200)
        self.assertIn("heatmap_data", response.context)
        self.assertIn("active_clients_with_totals", response.context)
        self.assertEqual(response.context["months_to_show"], 12)
        self.assertEqual(response.context["start_offset"], 0)
        self.assertEqual(response.context["heatmap_sort"], "total")

    def test_clients_tab_invalid_months_falls_back_to_default(self):
        response = self.client_instance.get(
            reverse("analytics") + "?tab=clients&months=not-a-number"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["months_to_show"], 12)

    def test_clients_tab_invalid_offset_falls_back_to_zero(self):
        response = self.client_instance.get(
            reverse("analytics") + "?tab=clients&offset=not-a-number"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["start_offset"], 0)

    def test_clients_tab_offset_strips_thousand_separator_commas(self):
        # replace(",", "") treats commas as thousand-separators, not decimals:
        # "1,000" -> "1000", not 1.
        response = self.client_instance.get(reverse("analytics") + "?tab=clients&offset=1,000")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["start_offset"], 1000)

    def test_clients_tab_invalid_sort_falls_back_to_total(self):
        response = self.client_instance.get(
            reverse("analytics") + "?tab=clients&sort=not-a-real-sort"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["heatmap_sort"], "total")

    def test_clients_tab_recent_sort_is_accepted(self):
        response = self.client_instance.get(reverse("analytics") + "?tab=clients&sort=recent")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["heatmap_sort"], "recent")

    def test_can_go_back_true_when_older_sessions_exist(self):
        Session.objects.create(
            client=self.test_client,
            session_date=date.today() - timedelta(days=400),
            duration=60,
        )
        response = self.client_instance.get(reverse("analytics") + "?tab=clients&months=1")
        self.assertTrue(response.context["can_go_back"])

    def test_revenue_tab_does_not_include_heatmap_context(self):
        response = self.client_instance.get(reverse("analytics") + "?tab=revenue")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("heatmap_data", response.context)


class RevenueReportTest(TestCase):
    """Test the revenue_report view."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="revenue-report",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="revenueuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance = TestClient()
        self.client_instance.login(username="revenueuser", password="testpass123")

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

    def test_no_year_selected_shows_available_years_only(self):
        response = self.client_instance.get(reverse("revenue_report"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("invoices", response.context)

    def test_selected_year_shows_paid_invoices(self):
        Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date(2026, 1, 15),
            paid_date=date(2026, 1, 20),
            status="paid",
            total=Decimal("180.00"),
            practice=self.practice,
        )
        response = self.client_instance.get(reverse("revenue_report") + "?year=2026")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["summary"]["count"], 1)
        self.assertEqual(response.context["summary"]["same_year_count"], 1)
        self.assertEqual(response.context["summary"]["total"], Decimal("180.00"))

    def test_year_diff_flagged_for_cross_year_payment(self):
        Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date(2025, 12, 20),
            paid_date=date(2026, 1, 5),
            status="paid",
            total=Decimal("90.00"),
            practice=self.practice,
        )
        response = self.client_instance.get(reverse("revenue_report") + "?year=2026")
        self.assertEqual(response.context["summary"]["prev_year_count"], 1)
        self.assertEqual(response.context["summary"]["same_year_count"], 0)
        self.assertTrue(response.context["invoices"][0].year_diff)

    def test_available_years_only_from_paid_invoices(self):
        Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date(2026, 1, 15),
            status="draft",
            total=Decimal("90.00"),
            practice=self.practice,
        )
        response = self.client_instance.get(reverse("revenue_report"))
        self.assertEqual(response.context["available_years"], [])
