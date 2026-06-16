"""
Tests for invoice_helpers utility functions.
"""

from decimal import Decimal

from django.test import TestCase
from my_practice.models import Client, Invoice, Practice, ServiceType
from my_practice.utils.invoice_helpers import get_next_invoice_number


class GetNextInvoiceNumberTests(TestCase):
    """Tests for the get_next_invoice_number() function."""

    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="invoice_helpers-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Create test clients
        self.client_bk = Client.objects.create(
            client_code="BK",
            full_name="Test Client BK",
            email="bk@test.com",
            hourly_rate_60=Decimal("100.00"),
            hourly_rate_90=Decimal("150.00"),
            practice=self.practice,
        )
        self.client_gm = Client.objects.create(
            client_code="GM",
            full_name="Test Client GM",
            email="gm@test.com",
            hourly_rate_60=Decimal("120.00"),
            hourly_rate_90=Decimal("180.00"),
            practice=self.practice,
        )

        # Create service type
        self.service_type = ServiceType.objects.create(
            code="individual",
            name_de="Einzelsitzung",
            name_en="Individual Session",
            practice=self.practice,
        )

    def test_first_invoice_for_client(self):
        """Test that first invoice gets number 1."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        result = get_next_invoice_number(self.client_bk)
        self.assertEqual(result, "BK-1")

    def test_sequential_numbering(self):
        """Test that invoice numbers increment sequentially."""
        # Create first invoice
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK-1",
            total=Decimal("100.00"),
            status="draft",
            practice=self.practice,
        )

        # Next should be BK-2
        result = get_next_invoice_number(self.client_bk)
        self.assertEqual(result, "BK-2")

        # Create second invoice
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK-2",
            total=Decimal("100.00"),
            status="draft",
            practice=self.practice,
        )

        # Next should be BK-3
        result = get_next_invoice_number(self.client_bk)
        self.assertEqual(result, "BK-3")

    def test_multiple_clients_independent(self):
        """Test that different clients have independent numbering."""
        # Create invoices for BK
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK-1",
            total=Decimal("100.00"),
            status="draft",
            practice=self.practice,
        )
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK-2",
            total=Decimal("100.00"),
            status="draft",
            practice=self.practice,
        )

        # Create invoice for GM
        Invoice.objects.create(
            client=self.client_gm,
            invoice_number="GM-1",
            total=Decimal("120.00"),
            status="draft",
            practice=self.practice,
        )

        # BK should get BK-3
        result_bk = get_next_invoice_number(self.client_bk)
        self.assertEqual(result_bk, "BK-3")

        # GM should get GM-2
        result_gm = get_next_invoice_number(self.client_gm)
        self.assertEqual(result_gm, "GM-2")

    def test_gaps_in_numbering(self):
        """Test that gaps in numbering are handled (uses highest + 1)."""
        # Create invoices with gaps (BK-1, BK-5, BK-3)
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK-1",
            total=Decimal("100.00"),
            status="draft",
            practice=self.practice,
        )
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK-5",
            total=Decimal("100.00"),
            status="draft",
            practice=self.practice,
        )
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK-3",
            total=Decimal("100.00"),
            status="draft",
            practice=self.practice,
        )

        # Should return BK-6 (highest is 5)
        result = get_next_invoice_number(self.client_bk)
        self.assertEqual(result, "BK-6")

    def test_malformed_invoice_numbers(self):
        """Test handling of malformed invoice numbers."""
        # Create invoice with malformed number
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK-invalid",
            total=Decimal("100.00"),
            status="draft",
            practice=self.practice,
        )

        # Should fall back to 1
        result = get_next_invoice_number(self.client_bk)
        self.assertEqual(result, "BK-1")

        # Create another with no dash
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK1",
            total=Decimal("100.00"),
            status="draft",
            practice=self.practice,
        )

        # Should still fall back to 1 since no valid numbers found
        result = get_next_invoice_number(self.client_bk)
        self.assertEqual(result, "BK-1")

    def test_mixed_valid_and_invalid_numbers(self):
        """Test that valid numbers are used even with some invalid ones present."""
        # Create mix of valid and invalid
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK-3",
            total=Decimal("100.00"),
            status="draft",
            practice=self.practice,
        )
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK-invalid",
            total=Decimal("100.00"),
            status="draft",
            practice=self.practice,
        )
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK-7",
            total=Decimal("100.00"),
            status="draft",
            practice=self.practice,
        )

        # Should return BK-8 (highest valid is 7)
        result = get_next_invoice_number(self.client_bk)
        self.assertEqual(result, "BK-8")

    def test_three_letter_client_code(self):
        """Test with 3-letter client code."""
        client_abc = Client.objects.create(
            client_code="ABC",
            full_name="Test Client ABC",
            email="abc@test.com",
            hourly_rate_60=Decimal("100.00"),
            hourly_rate_90=Decimal("150.00"),
            practice=self.practice,
        )

        # First invoice
        result = get_next_invoice_number(client_abc)
        self.assertEqual(result, "ABC-1")

        # Create invoice and check next
        Invoice.objects.create(
            client=client_abc,
            invoice_number="ABC-1",
            total=Decimal("100.00"),
            status="draft",
            practice=self.practice,
        )

        result = get_next_invoice_number(client_abc)
        self.assertEqual(result, "ABC-2")

    def test_high_numbers(self):
        """Test with high invoice numbers."""
        # Create invoice with high number
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK-999",
            total=Decimal("100.00"),
            status="draft",
            practice=self.practice,
        )

        result = get_next_invoice_number(self.client_bk)
        self.assertEqual(result, "BK-1000")

    def test_only_other_client_invoices_exist(self):
        """Test that only invoices for the specific client are considered."""
        # Create invoices for GM only
        Invoice.objects.create(
            client=self.client_gm,
            invoice_number="GM-5",
            total=Decimal("120.00"),
            status="draft",
            practice=self.practice,
        )
        Invoice.objects.create(
            client=self.client_gm,
            invoice_number="GM-10",
            total=Decimal("120.00"),
            status="draft",
            practice=self.practice,
        )

        # BK should still get BK-1 (not affected by GM invoices)
        result = get_next_invoice_number(self.client_bk)
        self.assertEqual(result, "BK-1")

    def test_different_invoice_statuses(self):
        """Test that all invoices are counted regardless of status."""
        # Create invoices with different statuses
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK-1",
            total=Decimal("100.00"),
            status="draft",
            practice=self.practice,
        )
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK-2",
            total=Decimal("100.00"),
            status="sent",
            practice=self.practice,
        )
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK-3",
            total=Decimal("100.00"),
            status="paid",
            practice=self.practice,
        )
        Invoice.objects.create(
            client=self.client_bk,
            invoice_number="BK-4",
            total=Decimal("100.00"),
            status="cancelled",
            practice=self.practice,
        )

        # Should return BK-5 (all statuses counted)
        result = get_next_invoice_number(self.client_bk)
        self.assertEqual(result, "BK-5")
