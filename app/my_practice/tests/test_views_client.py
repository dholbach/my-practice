"""
Tests for client views: list, detail, create, edit and the client code suggestion.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import (
    Client,
    ClientTag,
    Invoice,
    InvoiceItem,
    Practice,
    ServiceType,
    Session,
    UserPractice,
    allow_issued_invoice_writes,
)
from .test_helpers import create_test_practice, create_test_user, select_practice


class ClientListViewTest(TestCase):
    """Test client list view."""

    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="views_client-1")

        self.user = create_test_user(self.practice, username="testuser", password="testpass123")
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser", password="testpass123")

        # Create test clients
        Client.objects.create(
            client_code="CL1",
            full_name="Client One",
            email="client1@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

        Client.objects.create(
            client_code="CL2",
            full_name="Client Two",
            email="client2@example.com",
            hourly_rate_60=Decimal("100.00"),
            practice=self.practice,
        )

    def test_client_list_loads(self):
        """Test that client list loads successfully."""
        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="test-practice")

        response = self.client_instance.get(reverse("client_list"))
        self.assertEqual(response.status_code, 200)

    def test_client_list_shows_clients(self):
        """Test that all clients are displayed."""
        response = self.client_instance.get(reverse("client_list"))
        self.assertEqual(response.status_code, 200)
        # Check clients are in context (may be paginated)

    def test_client_list_search(self):
        """Test client list search functionality."""
        # Test search if implemented
        response = self.client_instance.get(reverse("client_list") + "?q=One")
        self.assertEqual(response.status_code, 200)

    def test_client_list_search_param_filters_results(self):
        """The ?search= param matches on client_code via icontains."""
        response = self.client_instance.get(reverse("client_list") + "?search=CL1")
        self.assertEqual(response.status_code, 200)
        codes = {c.client_code for c in response.context["clients"]}
        self.assertIn("CL1", codes)
        self.assertNotIn("CL2", codes)

    def test_client_list_multi_word_search_miss_returns_nothing(self):
        """
        Regression: the ?search= filter used `SearchRank(...) > 0` as its match
        test. ts_rank only returns exactly 0.0 for a single-lexeme miss; a
        multi-lexeme miss scores 1e-20, so any two-word search listed every
        client in the practice. A one-word miss passed all along, which is why
        the existing coverage never caught it.
        """
        response = self.client_instance.get(reverse("client_list") + "?search=Zzz+Qqq")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c.client_code for c in response.context["clients"]], [])

    def test_client_list_full_name_search_still_matches(self):
        response = self.client_instance.get(reverse("client_list") + "?search=Client+One")
        self.assertEqual(response.status_code, 200)
        codes = {c.client_code for c in response.context["clients"]}
        self.assertEqual(codes, {"CL1"})

    def test_client_list_tag_filter(self):
        """The ?tag= param restricts the list to clients with that tag."""
        tag = ClientTag.objects.create(name="follow-up", slug="follow-up")
        tagged_client = Client.objects.get(client_code="CL1")
        tagged_client.tags.add(tag)

        response = self.client_instance.get(reverse("client_list") + "?tag=follow-up")
        self.assertEqual(response.status_code, 200)
        codes = {c.client_code for c in response.context["clients"]}
        self.assertEqual(codes, {"CL1"})


class ClientDetailViewTest(TestCase):
    """Test client detail view."""

    @allow_issued_invoice_writes()
    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="views_client-2")

        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser", password="testpass123")

        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)

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

        # Create invoice for client
        self.invoice = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            total=Decimal("180.00"),
            status="paid",
            practice=self.practice,
        )

        session = Session.objects.create(
            client=self.test_client,
            session_date=date.today(),
            duration=60,
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=session,
            rate=Decimal("90.00"),
            quantity=Decimal("2.00"),
            total=Decimal("180.00"),
        )

    def test_client_detail_loads(self):
        """Test that client detail loads successfully."""
        response = self.client_instance.get(
            reverse("client_detail", kwargs={"pk": self.test_client.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_client_detail_renders_every_tab(self):
        """Each page tab is its own include; a dropped include would lose a whole tab."""
        response = self.client_instance.get(
            reverse("client_detail", kwargs={"pk": self.test_client.pk})
        )
        for tab in ("ptab-profil", "ptab-protokoll", "ptab-abrechnung"):
            self.assertContains(response, f'id="{tab}"')

    def test_client_detail_has_client(self):
        """Test that client is in context."""
        response = self.client_instance.get(
            reverse("client_detail", kwargs={"pk": self.test_client.pk})
        )
        self.assertIn("client", response.context)
        self.assertEqual(response.context["client"].client_code, "TC")

    def test_client_detail_shows_invoices(self):
        """Test that client invoices are displayed."""
        response = self.client_instance.get(
            reverse("client_detail", kwargs={"pk": self.test_client.pk})
        )
        client_obj = response.context["client"]
        # Invoices accessible via related name
        invoices_count = client_obj.invoices.count()
        self.assertEqual(invoices_count, 1)

    def test_client_detail_404(self):
        """Test 404 for non-existent client."""
        response = self.client_instance.get(reverse("client_detail", kwargs={"pk": 99999}))
        self.assertEqual(response.status_code, 404)

    def test_open_amount_is_exact_decimal_not_float_rounded(self):
        """open_amount must stay Decimal-exact; summing as float can introduce rounding drift."""
        for i in range(3):
            Invoice.objects.create(
                client=self.test_client,
                invoice_number=f"TC-OPEN-{i}",
                invoice_date=date.today(),
                total=Decimal("0.10"),
                status="sent",
                practice=self.practice,
            )
        response = self.client_instance.get(
            reverse("client_detail", kwargs={"pk": self.test_client.pk})
        )
        open_amount = response.context["stats"]["open_amount"]
        self.assertEqual(open_amount, Decimal("0.30"))
        self.assertIsInstance(open_amount, Decimal)


class ClientCreateViewTest(TestCase):
    """Test client creation view."""

    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="views_client-3")

        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.client_instance = TestClient()
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance.login(username="testuser", password="testpass123")
        select_practice(self.client_instance, self.practice)

    def test_client_create_loads(self):
        """Test that client create form loads."""
        response = self.client_instance.get(reverse("client_intake"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertContains(response, "Klient:in speichern")  # Create button text

    def test_client_create_form_submission(self):
        """Test creating a new client."""
        data = {
            "client_code": "TEST001",
            "full_name": "Test Client",
            "email": "test@example.com",
            "phone": "123-456-7890",
            "language": "de",
            "salutation": "Herr",
            "hourly_rate_60": "90.00",
            "hourly_rate_90": "130.00",
            "cancellation_fee": "0.00",
            "active": True,
        }
        response = self.client_instance.post(reverse("client_intake"), data)

        # Should redirect to client list
        self.assertEqual(response.status_code, 302)

        # Client should be created
        self.assertTrue(Client.objects.filter(client_code="TEST001").exists())
        new_client = Client.objects.get(client_code="TEST001")
        self.assertEqual(new_client.full_name, "Test Client")

    def test_client_create_duplicate_code(self):
        """Test that duplicate client codes are rejected."""
        # Create first client
        Client.objects.create(
            client_code="DUP001",
            full_name="First Client",
            email="first@example.com",
            practice=self.practice,
        )

        # Try to create second client with same code
        data = {
            "client_code": "DUP001",  # Duplicate!
            "full_name": "Second Client",
            "email": "second@example.com",
        }
        response = self.client_instance.post(reverse("client_intake"), data)

        # Should show form again with error
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        # Form should have errors
        self.assertTrue(response.context["form"].errors)


class ClientIntakeEditTest(TestCase):
    """Test ClientIntakeView in edit mode (get_object with a pk in the URL)."""

    def setUp(self):
        self.practice = create_test_practice(name="Test Practice", slug="intake-edit")
        self.user = create_test_user(self.practice, username="edituser", password="testpass123")
        self.http = TestClient()
        self.http.login(username="edituser", password="testpass123")

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            practice=self.practice,
        )

    def test_edit_loads_existing_client(self):
        response = self.http.get(reverse("client_edit", kwargs={"pk": self.test_client.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].instance.pk, self.test_client.pk)

    def test_edit_nonexistent_client_404s(self):
        response = self.http.get(reverse("client_edit", kwargs={"pk": 99999}))
        self.assertEqual(response.status_code, 404)


class SuggestClientCodeTest(TestCase):
    """Tests for the suggest_client_code endpoint."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Suggest Test Practice",
            slug="suggest-test",
            title="Test",
            email="suggest@test.example",
            city="Berlin",
        )
        self.user = User.objects.create_user("suggest_user", password="pw")
        UserPractice.objects.create(user=self.user, practice=self.practice)
        self.client_browser = TestClient()
        self.client_browser.login(username="suggest_user", password="pw")
        select_practice(self.client_browser, self.practice)

    def _get(self, name=""):
        return self.client_browser.get(reverse("suggest_client_code"), {"name": name})

    def test_empty_name_returns_empty(self):
        resp = self._get("")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["suggestions"], [])

    def test_name_with_no_alpha_characters_returns_empty(self):
        resp = self._get("123 456")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["suggestions"], [])

    def test_two_part_name_suggests_initials_first(self):
        resp = self._get("Anna Schmidt")
        suggestions = resp.json()["suggestions"]
        self.assertIn("AS", suggestions)
        self.assertEqual(suggestions[0], "AS")

    def test_two_part_name_includes_two_letter_variants(self):
        resp = self._get("Anna Schmidt")
        suggestions = resp.json()["suggestions"]
        self.assertIn("AN", suggestions)
        self.assertIn("SC", suggestions)

    def test_taken_codes_are_excluded(self):
        Client.objects.create(
            practice=self.practice,
            full_name="Max Mustermann",
            client_code="AS",
        )
        suggestions = self._get("Anna Schmidt").json()["suggestions"]
        self.assertNotIn("AS", suggestions)
        self.assertIn("AN", suggestions)

    def test_three_letter_variants_included(self):
        suggestions = self._get("Anna Schmidt").json()["suggestions"]
        self.assertTrue(any(len(s) == 3 for s in suggestions))

    def test_single_word_name(self):
        resp = self._get("Anna")
        suggestions = resp.json()["suggestions"]
        self.assertIn("AN", suggestions)

    def test_max_six_suggestions_returned(self):
        suggestions = self._get("Anna Schmidt").json()["suggestions"]
        self.assertLessEqual(len(suggestions), 6)
