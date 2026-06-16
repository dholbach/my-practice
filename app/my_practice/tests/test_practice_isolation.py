"""
Tests for practice isolation - ensuring data is properly scoped by practice.
"""

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from my_practice.models import (
    Client,
    CompanyExpense,
    CompanyWithdrawal,
    Invoice,
    Practice,
)


class PracticeIsolationTestCase(TestCase):
    """Test that practices are properly isolated from each other"""

    def setUp(self):
        """Create two practices with test data"""
        # Create user
        self.user = User.objects.create_user(username="testuser", password="testpass")

        # Create two practices
        self.practice_a = Practice.objects.create(
            name="Practice A",
            slug="practice-a",
            title="Therapist A",
            street="Street A",
            postal_code="12345",
            city="City A",
            email="a@example.com",
            email_from_name="Practice A",
            website="https://a.example.com",
            bank_name="Bank A",
            iban="DE89370400440532013000",
            bic="COBADEFFXXX",
            tax_id="12345",
        )
        self.practice_a.users.add(self.user)

        self.practice_b = Practice.objects.create(
            name="Practice B",
            slug="practice-b",
            title="Therapist B",
            street="Street B",
            postal_code="54321",
            city="City B",
            email="b@example.com",
            email_from_name="Practice B",
            website="https://b.example.com",
            bank_name="Bank B",
            iban="DE89370400440532013001",
            bic="COBADEFFXXY",
            tax_id="54321",
        )
        self.practice_b.users.add(self.user)

        # Create clients for each practice
        self.client_a = Client.objects.create(
            practice=self.practice_a,
            client_code="CA",
            full_name="Client A",
            email="client_a@example.com",
            active=True,
        )

        self.client_b = Client.objects.create(
            practice=self.practice_b,
            client_code="CB",
            full_name="Client B",
            email="client_b@example.com",
            active=True,
        )

        # Create request factory
        self.factory = RequestFactory()

    def test_client_queryset_isolation(self):
        """Test that clients are properly scoped by practice"""
        # Setup request for practice A
        request = self.factory.get("/")
        request.user = self.user
        request.current_practice = self.practice_a

        # Query clients with practice A context
        clients_a = Client.objects.for_current_practice(request)
        self.assertEqual(clients_a.count(), 1)
        self.assertEqual(clients_a.first().client_code, "CA")

        # Switch to practice B
        request.current_practice = self.practice_b
        clients_b = Client.objects.for_current_practice(request)
        self.assertEqual(clients_b.count(), 1)
        self.assertEqual(clients_b.first().client_code, "CB")

    def test_cross_practice_access_denied(self):
        """Test that accessing another practice's client fails"""
        request = self.factory.get("/")
        request.user = self.user
        request.current_practice = self.practice_a

        # Try to access client from practice B while in practice A context
        clients = Client.objects.for_current_practice(request).filter(pk=self.client_b.pk)
        self.assertEqual(clients.count(), 0)

    def test_invoice_isolation(self):
        """Test that invoices are scoped by practice"""
        # Create invoices for each practice
        Invoice.objects.create(
            practice=self.practice_a,
            client=self.client_a,
            invoice_number="A-001",
            status="draft",
        )

        Invoice.objects.create(
            practice=self.practice_b,
            client=self.client_b,
            invoice_number="B-001",
            status="draft",
        )

        # Test practice A context
        request = self.factory.get("/")
        request.user = self.user
        request.current_practice = self.practice_a

        invoices_a = Invoice.objects.for_current_practice(request)
        self.assertEqual(invoices_a.count(), 1)
        self.assertEqual(invoices_a.first().invoice_number, "A-001")

        # Test practice B context
        request.current_practice = self.practice_b
        invoices_b = Invoice.objects.for_current_practice(request)
        self.assertEqual(invoices_b.count(), 1)
        self.assertEqual(invoices_b.first().invoice_number, "B-001")

    def test_withdrawal_isolation(self):
        """Test that withdrawals are scoped by practice"""
        from datetime import date

        CompanyWithdrawal.objects.create(
            practice=self.practice_a,
            date=date.today(),
            amount=1000,
            category="salary",
        )

        CompanyWithdrawal.objects.create(
            practice=self.practice_b,
            date=date.today(),
            amount=2000,
            category="salary",
        )

        # Test practice A context
        request = self.factory.get("/")
        request.user = self.user
        request.current_practice = self.practice_a

        withdrawals_a = CompanyWithdrawal.objects.for_current_practice(request)
        self.assertEqual(withdrawals_a.count(), 1)
        self.assertEqual(withdrawals_a.first().amount, 1000)

        # Test practice B context
        request.current_practice = self.practice_b
        withdrawals_b = CompanyWithdrawal.objects.for_current_practice(request)
        self.assertEqual(withdrawals_b.count(), 1)
        self.assertEqual(withdrawals_b.first().amount, 2000)

    def test_expense_isolation(self):
        """Test that expenses are scoped by practice"""
        from datetime import date

        CompanyExpense.objects.create(
            practice=self.practice_a,
            date=date.today(),
            amount=100,
            category="miete",
        )

        CompanyExpense.objects.create(
            practice=self.practice_b,
            date=date.today(),
            amount=200,
            category="telefon",
        )

        # Test practice A context
        request = self.factory.get("/")
        request.user = self.user
        request.current_practice = self.practice_a

        expenses_a = CompanyExpense.objects.for_current_practice(request)
        self.assertEqual(expenses_a.count(), 1)
        self.assertEqual(expenses_a.first().category, "miete")

        # Test practice B context
        request.current_practice = self.practice_b
        expenses_b = CompanyExpense.objects.for_current_practice(request)
        self.assertEqual(expenses_b.count(), 1)
        self.assertEqual(expenses_b.first().category, "telefon")

    def test_create_without_practice_raises_integrity_error(self):
        """practice_id is NOT NULL — creating a client without a practice is rejected at DB level"""
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            Client.objects.create(
                client_code="OR",
                full_name="Orphan Client",
                email="orphan@example.com",
                active=True,
                # practice=None — should be rejected by DB constraint
            )
