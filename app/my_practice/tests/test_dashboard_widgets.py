"""Tests for dashboard widget builders."""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from ..models import Client, Invoice
from ..utils.dashboard_widgets import InvoiceActionsWidgetBuilder
from .test_helpers import create_test_invoice, create_test_practice


class GetOverdueInvoicesTest(TestCase):
    """
    InvoiceActionsWidgetBuilder.get_overdue_invoices() should honor
    practice.overdue_after_days instead of a hardcoded 30-day cutoff (#195).
    """

    def setUp(self):
        self.practice = create_test_practice(name="Test Practice", slug="dashboard-widgets-1")
        self.client_obj = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

    def _make_invoice(self, days_old: int) -> Invoice:
        return create_test_invoice(
            self.client_obj,
            f"TC-{days_old}",
            Invoice.Status.SENT,
            date.today() - timedelta(days=days_old),
            total=Decimal("90.00"),
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

    def test_given_the_unpaid_list_it_does_not_query_again(self):
        self._make_invoice(days_old=31)
        builder = InvoiceActionsWidgetBuilder(self.practice)
        unpaid = list(builder._get_unpaid_invoices())

        with self.assertNumQueries(0):
            overdue = builder.get_overdue_invoices(unpaid=unpaid)

        self.assertEqual([inv.invoice_number for inv in overdue], ["TC-31"])
