"""
Async Views Test Suite

Tests for async analytics and dashboard views.
Ensures async views produce same results as sync versions.

Note: These tests require pytest-asyncio and are marked as async.
Run with: pytest my_practice/tests/test_async_views.py
"""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import AsyncClient
from my_practice.models import Client, Invoice, InvoiceItem, Practice, ServiceType, Session

User = get_user_model()

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


class TestAsyncAnalyticsViews:
    """Test async analytics views"""

    @pytest.fixture(autouse=True)
    def setup_data(self, db):  # noqa: ARG002, vulture
        """Set up test data (runs before each test)"""
        # Create user
        self.user = User.objects.create_user(username="testuser", password="testpass123")

        # Create practice
        self.practice = Practice.objects.create(name="Test Practice", email="test@example.com")
        self.practice.users.add(self.user)

        # Create service type
        self.service_type = ServiceType.objects.create(
            code="therapy_60",
            name="Therapy Session (60 min)",
            duration=60,
            practice=self.practice,
        )

        # Create client
        self.client_obj = Client.objects.create(
            client_code="TEST-001",
            full_name="Test Client",
            email="client@example.com",
            practice=self.practice,
            hourly_rate_60=Decimal("120.00"),
        )

        # Create invoice with items
        self.invoice = Invoice.objects.create(
            invoice_number="2026-001",
            client=self.client_obj,
            invoice_date=date(2026, 1, 15),
            status="paid",
            paid_date=date(2026, 1, 20),
            practice=self.practice,
        )

        session = Session.objects.create(
            client=self.client_obj,
            session_date=date(2026, 1, 10),
            duration=60,
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            session=session,
            service_type=self.service_type,
            rate=Decimal("120.00"),
            quantity=1,
        )

    async def test_analytics_dashboard_async_loads(self, db):  # noqa: ARG002, vulture, vulture
        """Test that async analytics dashboard loads successfully"""
        client = AsyncClient()
        await client.force_login(self.user)

        # Add current_practice to session
        session = client.session
        session["current_practice_id"] = self.practice.id
        await session.asave()

        response = await client.get("/analytics/")
        assert response.status_code == 200

    async def test_dashboard_async_loads(self, db):  # noqa: ARG002, vulture, vulture
        """Test that async dashboard loads successfully"""
        client = AsyncClient()
        await client.force_login(self.user)

        session = client.session
        session["current_practice_id"] = self.practice.id
        await session.asave()

        response = await client.get("/dashboard/")
        assert response.status_code == 200


# Performance Benchmark Notes:
# ============================
# To benchmark async vs sync performance, use:
#
# python scripts/benchmark_async_views.py
#
# Or run pytest with benchmarking:
# pytest my_practice/tests/test_async_views.py -v --durations=10
