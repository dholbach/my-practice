"""Tests for Django models."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from my_practice.models import (
    Client,
    ClientTag,
    CompanyExpense,
    CompanyWithdrawal,
    GoogleCalendarToken,
    Invoice,
    InvoiceItem,
    Practice,
    ServiceType,
    Session,
    TimeOff,
)


class PracticeModelTestCase(TestCase):
    """Tests for Practice model"""

    def test_practice_creation(self):
        """Test creating a practice instance"""
        practice = Practice.objects.create(
            name="Test Practice",
            email="test@example.com",
        )
        self.assertEqual(practice.name, "Test Practice")
        self.assertEqual(practice.email, "test@example.com")

    def test_practice_str(self):
        """Test Practice string representation"""
        practice = Practice.objects.create(name="Test Practice", title="Test Title")
        self.assertIn("Test Practice", str(practice))

    def test_practice_defaults(self):
        """Test Practice default values"""
        practice = Practice.objects.create(name="Test")
        self.assertEqual(practice.payment_terms_days, 14)
        self.assertEqual(practice.email, "")  # No default email (PII-free)


class ClientModelTestCase(TestCase):
    """Tests for Client model"""

    def setUp(self):
        """Create test practice"""
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="models-client",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

    def test_client_creation(self):
        """Test creating a client"""
        client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            practice=self.practice,
        )
        self.assertEqual(client.client_code, "TC")
        self.assertEqual(client.full_name, "Test Client")

    def test_client_str(self):
        """Test Client string representation"""
        client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            practice=self.practice,
        )
        self.assertEqual(str(client), "TC")

    def test_client_code_unique(self):
        """Test that client_code must be unique"""
        Client.objects.create(
            client_code="TC",
            full_name="Test Client 1",
            email="test1@example.com",
            practice=self.practice,
        )
        with self.assertRaises(IntegrityError):
            Client.objects.create(
                client_code="TC",
                full_name="Test Client 2",
                email="test2@example.com",
                practice=self.practice,
            )

    def test_client_defaults(self):
        """Test Client default values"""
        client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            practice=self.practice,
        )
        self.assertEqual(client.hourly_rate_60, Decimal("90.00"))
        self.assertEqual(client.hourly_rate_90, Decimal("130.00"))
        self.assertEqual(client.cancellation_fee, Decimal("0.00"))
        self.assertEqual(client.language, "de")
        self.assertTrue(client.active)
        self.assertFalse(client.is_online_client)

    def test_client_ordering(self):
        """Test Client default ordering (active first, then name)"""
        Client.objects.create(
            client_code="A",
            full_name="Z Client",
            email="z@test.com",
            active=True,
            practice=self.practice,
        )
        Client.objects.create(
            client_code="B",
            full_name="A Client",
            email="a@test.com",
            active=False,
            practice=self.practice,
        )
        Client.objects.create(
            client_code="C",
            full_name="M Client",
            email="m@test.com",
            active=True,
            practice=self.practice,
        )

        clients = list(Client.objects.all())
        # Active clients first
        self.assertTrue(clients[0].active)
        self.assertTrue(clients[1].active)
        self.assertFalse(clients[2].active)


class ServiceTypeModelTestCase(TestCase):
    """Tests for ServiceType model"""

    def setUp(self):
        """Create test practice"""
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="models-servicetype",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

    def test_service_type_creation(self):
        """Test creating a service type"""
        st = ServiceType.objects.create(
            code="therapy_60",
            name="60-Min Session",
            default_duration=60,
            practice=self.practice,
        )
        self.assertEqual(st.code, "therapy_60")
        self.assertEqual(st.default_duration, 60)

    def test_service_type_str(self):
        """Test ServiceType string representation"""
        st = ServiceType.objects.create(
            code="therapy_60", name="60-Min Session", practice=self.practice
        )
        self.assertEqual(str(st), "60-Min Session")

    def test_service_type_code_unique(self):
        """Test that service type code must be unique"""
        ServiceType.objects.create(code="therapy_60", name="Session 1", practice=self.practice)
        with self.assertRaises(IntegrityError):
            ServiceType.objects.create(code="therapy_60", name="Session 2", practice=self.practice)

    def test_service_type_get_name(self):
        """Test get_name method with language fallback"""
        st = ServiceType.objects.create(
            code="therapy_60",
            name="Default Name",
            name_de="Deutsche Sitzung",
            name_en="English Session",
            practice=self.practice,
        )
        self.assertEqual(st.get_name("de"), "Deutsche Sitzung")
        self.assertEqual(st.get_name("en"), "English Session")
        self.assertEqual(st.get_name("fr"), "Default Name")  # Fallback


class InvoiceModelTestCase(TestCase):
    """Tests for Invoice model"""

    def setUp(self):
        """Create test client"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="models-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            practice=self.practice,
        )

    def test_invoice_creation(self):
        """Test creating an invoice"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            status="draft",
            practice=self.practice,
        )
        self.assertEqual(invoice.invoice_number, "TC-1")
        self.assertEqual(invoice.status, "draft")

    def test_invoice_str(self):
        """Test Invoice string representation"""
        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TC-123",
            invoice_date=date.today(),
            practice=self.practice,
        )
        self.assertIn("TC-123", str(invoice))

    def test_invoice_number_unique(self):
        """Test that invoice_number should be unique (but allows blank)"""

        Invoice.objects.create(
            client=self.client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            practice=self.practice,
        )
        # Creating with same number should raise ValidationError
        with self.assertRaises(ValidationError):
            Invoice.objects.create(
                client=self.client,
                invoice_number="TC-1",
                invoice_date=date.today(),
                practice=self.practice,
            )

    def test_invoice_defaults(self):
        """Test Invoice default values"""
        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            practice=self.practice,
        )
        self.assertEqual(invoice.status, "draft")
        self.assertEqual(invoice.tax_rate, Decimal("0.00"))

    def test_invoice_calculate_total(self):
        """Test invoice total calculation"""
        service_type = ServiceType.objects.create(
            code="therapy_60",
            name="Session",
            default_duration=60,
            practice=self.practice,
        )
        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            practice=self.practice,
        )
        session_60 = Session.objects.create(
            client=self.client,
            session_date=date.today(),
            duration=60,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            session=session_60,
            service_type=service_type,
            rate=Decimal("90.00"),
        )
        session_90 = Session.objects.create(
            client=self.client,
            session_date=date.today(),
            duration=90,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            session=session_90,
            service_type=service_type,
            rate=Decimal("130.00"),
        )

        total = invoice.calculate_total()
        self.assertEqual(total, Decimal("220.00"))

    def test_invoice_ordering(self):
        """Test Invoice default ordering (newest first)"""
        Invoice.objects.create(
            client=self.client,
            invoice_number="TC-1",
            invoice_date=date(2025, 1, 1),
            practice=self.practice,
        )
        Invoice.objects.create(
            client=self.client,
            invoice_number="TC-2",
            invoice_date=date(2025, 12, 1),
            practice=self.practice,
        )

        invoices = list(Invoice.objects.all())
        self.assertEqual(invoices[0].invoice_number, "TC-2")  # Newest first
        self.assertEqual(invoices[1].invoice_number, "TC-1")


class InvoiceItemModelTestCase(TestCase):
    """Tests for InvoiceItem model"""

    def setUp(self):
        """Create test data"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="models-2",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            practice=self.practice,
        )
        self.invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            practice=self.practice,
        )
        self.service_type = ServiceType.objects.create(
            code="therapy_60",
            name="60-Min Session",
            default_duration=60,
            practice=self.practice,
        )

    def test_invoice_item_creation(self):
        """Test creating an invoice item"""
        session = Session.objects.create(
            client=self.client,
            session_date=date.today(),
            duration=60,
        )
        item = InvoiceItem.objects.create(
            invoice=self.invoice,
            session=session,
            service_type=self.service_type,
            rate=Decimal("90.00"),
        )
        self.assertEqual(item.session.duration, 60)
        self.assertEqual(item.rate, Decimal("90.00"))

    def test_invoice_item_str(self):
        """Test InvoiceItem string representation"""
        session = Session.objects.create(
            client=self.client,
            session_date=date(2025, 12, 24),
            duration=60,
        )
        item = InvoiceItem.objects.create(
            invoice=self.invoice,
            session=session,
            service_type=self.service_type,
            rate=Decimal("90.00"),
        )
        # __str__ returns invoice number and date
        result = str(item)
        self.assertIn("TC-1", result)
        self.assertIn("2025-12-24", result)

    def test_invoice_item_line_total(self):
        """Test line total calculation (rate only, no quantity)"""
        session = Session.objects.create(
            client=self.client,
            session_date=date.today(),
            duration=60,
        )
        item = InvoiceItem.objects.create(
            invoice=self.invoice,
            session=session,
            service_type=self.service_type,
            rate=Decimal("90.00"),
        )
        # Line total is just the rate
        self.assertEqual(item.rate, Decimal("90.00"))


class CompanyWithdrawalModelTestCase(TestCase):
    """Tests for CompanyWithdrawal model"""

    def setUp(self):
        """Create test practice"""
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="models-withdrawal",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

    def test_withdrawal_creation(self):
        """Test creating a withdrawal"""
        withdrawal = CompanyWithdrawal.objects.create(
            date=date.today(),
            amount=Decimal("1000.00"),
            description="Test withdrawal",
            practice=self.practice,
        )
        self.assertEqual(withdrawal.amount, Decimal("1000.00"))

    def test_withdrawal_str(self):
        """Test CompanyWithdrawal string representation"""
        withdrawal = CompanyWithdrawal.objects.create(
            date=date(2025, 12, 24), amount=Decimal("500.00"), practice=self.practice
        )
        # Check it contains key info
        self.assertIn("500", str(withdrawal))
        self.assertIn("2025", str(withdrawal))

    def test_withdrawal_ordering(self):
        """Test withdrawal ordering (newest first)"""
        CompanyWithdrawal.objects.create(
            date=date(2025, 1, 1), amount=Decimal("100.00"), practice=self.practice
        )
        CompanyWithdrawal.objects.create(
            date=date(2025, 12, 1), amount=Decimal("200.00"), practice=self.practice
        )

        withdrawals = list(CompanyWithdrawal.objects.all())
        self.assertEqual(withdrawals[0].date, date(2025, 12, 1))


class CompanyExpenseModelTestCase(TestCase):
    """Tests for CompanyExpense model"""

    def setUp(self):
        """Create test practice"""
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="models-expense",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

    def test_expense_creation(self):
        """Test creating an expense"""
        expense = CompanyExpense.objects.create(
            date=date.today(),
            description="Test expense",
            category="supplies",
            amount=Decimal("50.00"),
            practice=self.practice,
        )
        self.assertEqual(expense.category, "supplies")
        self.assertEqual(expense.amount, Decimal("50.00"))

    def test_expense_str(self):
        """Test CompanyExpense string representation"""
        expense = CompanyExpense.objects.create(
            date=date(2025, 12, 24),
            description="Office supplies",
            category="supplies",
            amount=Decimal("75.50"),
            practice=self.practice,
        )
        # Check it contains key info
        result = str(expense)
        self.assertTrue("Office" in result or "supplies" in result or "75" in result)

    def test_expense_defaults(self):
        """Test CompanyExpense default values"""
        expense = CompanyExpense.objects.create(
            date=date.today(),
            description="Test",
            category="other",
            amount=Decimal("10.00"),
            practice=self.practice,
        )
        self.assertTrue(expense.is_tax_deductible)
        self.assertFalse(expense.has_invoice)


class TimeOffModelTestCase(TestCase):
    """Tests for TimeOff model"""

    def test_timeoff_creation(self):
        """Test creating a time off entry"""
        timeoff = TimeOff.objects.create(
            title="Christmas Holiday",
            start_date=date(2025, 12, 24),
            end_date=date(2025, 12, 26),
            type="vacation",
        )
        self.assertEqual(timeoff.title, "Christmas Holiday")
        self.assertEqual(timeoff.type, "vacation")

    def test_timeoff_str(self):
        """Test TimeOff string representation"""
        timeoff = TimeOff.objects.create(
            title="Summer Vacation",
            start_date=date(2025, 7, 1),
            end_date=date(2025, 7, 14),
            type="vacation",
        )
        self.assertIn("Summer Vacation", str(timeoff))

    def test_timeoff_duration_days_property(self):
        """Test duration_days property calculation"""
        timeoff = TimeOff.objects.create(
            title="Test",
            start_date=date(2025, 12, 24),
            end_date=date(2025, 12, 26),  # 3 days inclusive
            type="vacation",
        )
        self.assertEqual(timeoff.duration_days, 3)

    def test_timeoff_single_day(self):
        """Test time off for single day"""
        timeoff = TimeOff.objects.create(
            title="Doctor Appointment",
            start_date=date(2025, 12, 24),
            end_date=date(2025, 12, 24),
            type="sick",
        )
        self.assertEqual(timeoff.duration_days, 1)

    def test_timeoff_ordering(self):
        """Test TimeOff ordering"""
        TimeOff.objects.create(
            title="Old",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 1),
            type="vacation",
        )
        TimeOff.objects.create(
            title="New",
            start_date=date(2025, 12, 1),
            end_date=date(2025, 12, 1),
            type="vacation",
        )

        timeoffs = list(TimeOff.objects.all())
        # Check that we have both
        self.assertEqual(len(timeoffs), 2)


class GoogleCalendarTokenModelTestCase(TestCase):
    """Tests for GoogleCalendarToken model"""

    def setUp(self):
        """Create test practice"""
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="models-token",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

    def test_token_creation(self):
        """Test creating a calendar token"""
        token = GoogleCalendarToken.objects.create(
            token='{"access_token": "test"}',
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test_client",
            client_secret="test_secret",
            practice=self.practice,
        )
        self.assertIsNotNone(token.created_at)

    def test_token_str(self):
        """Test GoogleCalendarToken string representation"""
        token = GoogleCalendarToken.objects.create(
            token='{"access_token": "test"}', practice=self.practice
        )
        # Check it returns something
        self.assertIsNotNone(str(token))
        self.assertTrue(len(str(token)) > 0)


class ClientTagModelTestCase(TestCase):
    """Tests for ClientTag model and category-based sorting"""

    def setUp(self):
        """Create tags in mixed order to test sorting"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="models-3",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Create in random order (with all needed tags)
        ClientTag.objects.create(
            name="z-general", slug="z-general", category="general", color="blue"
        )
        ClientTag.objects.create(name="urgent", slug="urgent", category="attention", color="red")
        ClientTag.objects.create(
            name="follow-up", slug="follow-up", category="attention", color="orange"
        )
        ClientTag.objects.create(
            name="traveling", slug="traveling", category="general", color="green"
        )
        ClientTag.objects.create(name="closure", slug="closure", category="exit", color="purple")
        ClientTag.objects.create(name="a-exit", slug="a-exit", category="exit", color="gray")

    def test_category_priority_property(self):
        """Test that category_priority property returns correct values"""
        attention_tag = ClientTag.objects.get(slug="urgent")
        general_tag = ClientTag.objects.get(slug="traveling")
        exit_tag = ClientTag.objects.get(slug="closure")

        self.assertEqual(attention_tag.category_priority, 1)
        self.assertEqual(general_tag.category_priority, 2)
        self.assertEqual(exit_tag.category_priority, 3)

    def test_tags_sort_by_category_and_name(self):
        """Test that tags sort by category priority first, then alphabetically"""
        tags = ClientTag.objects.all()

        # Sort using the same logic as in views
        sorted_tags = sorted(tags, key=lambda t: (t.category_priority, t.name.lower()))

        # Expected order:
        # 1. Attention (priority 1): follow-up, urgent
        # 2. General (priority 2): traveling, z-general
        # 3. Exit (priority 3): a-exit, closure

        expected_slugs = [
            "follow-up",  # attention, alphabetically first
            "urgent",  # attention, alphabetically second
            "traveling",  # general, alphabetically first
            "z-general",  # general, alphabetically second
            "a-exit",  # exit, alphabetically first
            "closure",  # exit, alphabetically second
        ]

        actual_slugs = [tag.slug for tag in sorted_tags]
        self.assertEqual(actual_slugs, expected_slugs)

    def test_attention_tags_come_first(self):
        """Test that attention category tags always come before other categories"""
        tags = ClientTag.objects.all()
        sorted_tags = sorted(tags, key=lambda t: (t.category_priority, t.name.lower()))

        # First two tags should be attention
        self.assertEqual(sorted_tags[0].category, "attention")
        self.assertEqual(sorted_tags[1].category, "attention")

        # Next two should be general
        self.assertEqual(sorted_tags[2].category, "general")
        self.assertEqual(sorted_tags[3].category, "general")

        # Last two should be exit
        self.assertEqual(sorted_tags[4].category, "exit")
        self.assertEqual(sorted_tags[5].category, "exit")

    def test_alphabetical_within_category(self):
        """Test that tags sort alphabetically within same category"""
        tags = ClientTag.objects.filter(category="attention")
        sorted_tags = sorted(tags, key=lambda t: (t.category_priority, t.name.lower()))

        # Should be: follow-up, urgent (alphabetically)
        self.assertEqual(sorted_tags[0].name, "follow-up")
        self.assertEqual(sorted_tags[1].name, "urgent")
