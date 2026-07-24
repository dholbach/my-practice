"""Tests for dashboard widget builders."""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from ..models import Client, Invoice, Practice
from ..utils.dashboard_widgets import InvoiceActionsWidgetBuilder


class GetOverdueInvoicesTest(TestCase):
    """
    InvoiceActionsWidgetBuilder.get_overdue_invoices() should honor
    practice.overdue_after_days instead of a hardcoded 30-day cutoff (#195).
    """

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="dashboard-widgets-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.client_obj = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

    def _make_invoice(self, days_old: int) -> Invoice:
        return Invoice.objects.create(
            client=self.client_obj,
            invoice_number=f"TC-{days_old}",
            invoice_date=date.today() - timedelta(days=days_old),
            total=Decimal("90.00"),
            status="sent",
            practice=self.practice,
        )

    def test_default_threshold_matches_previous_hardcoded_30_days(self):
        self._make_invoice(days_old=31)
        self._make_invoice(days_old=29)

        overdue = InvoiceActionsWidgetBuilder(self.practice).get_overdue_invoices()

        self.assertEqual([inv.invoice_number for inv in overdue], ["TC-31"])

    def test_custom_threshold_is_respected(self):
        self.practice.overdue_after_days = 10
        self.practice.save()
        self._make_invoice(days_old=15)
        self._make_invoice(days_old=5)

        overdue = InvoiceActionsWidgetBuilder(self.practice).get_overdue_invoices()

        self.assertEqual([inv.invoice_number for inv in overdue], ["TC-15"])
