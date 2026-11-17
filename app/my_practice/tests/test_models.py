"""
Tests for the core models: practice, client, service type, tags and client documents.
"""

from datetime import date
from decimal import Decimal

from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase

from my_practice.models import (
    Client,
    ClientTag,
    Practice,
    ServiceType,
)
from my_practice.utils.tag_helpers import sort_tags_by_category

from .test_helpers import create_test_practice


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
        self.practice = create_test_practice(name="Test Practice", slug="models-client")

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
        self.practice = create_test_practice(name="Test Practice", slug="models-servicetype")

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


class ClientTagModelTestCase(TestCase):
    """Tests for ClientTag model and category-based sorting"""

    def setUp(self):
        """Create tags in mixed order to test sorting"""
        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="models-3")

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

    def test_tags_sort_by_category_and_name(self):
        """Test that tags sort by category priority first, then alphabetically"""
        sorted_tags = sort_tags_by_category(ClientTag.objects.all())

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
        sorted_tags = sort_tags_by_category(ClientTag.objects.all())

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
        sorted_tags = sort_tags_by_category(ClientTag.objects.filter(category="attention"))

        # Should be: follow-up, urgent (alphabetically)
        self.assertEqual(sorted_tags[0].name, "follow-up")
        self.assertEqual(sorted_tags[1].name, "urgent")


class ClientDocumentUploadPathTest(SimpleTestCase):
    """client_document_upload_path builds a path from the free-text client code."""

    def _path(self, client_code):
        from types import SimpleNamespace

        from my_practice.models.client import client_document_upload_path

        instance = SimpleNamespace(
            client=SimpleNamespace(client_code=client_code),
            document_date=date(2026, 1, 15),
            document_type="contract",
        )
        return client_document_upload_path(instance, "Scan.PDF")

    def test_ordinary_code_is_lowercased(self):
        self.assertEqual(self._path("XX-1"), "clients/xx-1/2026/contract-2026-01-15-scan.pdf")

    def test_code_cannot_escape_clients_directory(self):
        path = self._path("../../x")
        self.assertTrue(path.startswith("clients/"))
        self.assertNotIn("..", path)
