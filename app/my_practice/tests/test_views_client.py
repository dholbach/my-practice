"""
Tests for client views.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import Client, Invoice, InvoiceItem, Practice, ServiceType, Session, UserPractice
from ..utils.tag_helpers import SESSION_LOG_MIN_DURATION


class ClientListViewTest(TestCase):
    """Test client list view."""

    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_client-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.user = User.objects.create_user(username="testuser", password="testpass123")
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
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

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


class ClientDetailViewTest(TestCase):
    """Test client detail view."""

    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_client-2",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

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


class NoLogNeededSessionIdsTest(TestCase):
    """
    Regression tests for no_log_needed_session_ids in client_detail context.

    When client.cancellation_fee equals the regular session rate, the old
    rate-based detection incorrectly suppressed + Protokoll on all billed
    sessions. Now detection uses service_type__name__icontains='cancel'.
    """

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="no-log-test",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="nluser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.http = TestClient()
        self.http.login(username="nluser", password="testpass123")

        # Both service types billed at the SAME rate — the historical bug trigger
        self.stype_regular = ServiceType.objects.create(
            code="regular",
            name="60-Min Therapy Session",
            practice=self.practice,
        )
        self.stype_cancel = ServiceType.objects.create(
            code="cancel",
            name="Cancellation Fee",
            practice=self.practice,
        )

        # Client with cancellation_fee == regular session rate
        self.pat = Client.objects.create(
            client_code="NL1",
            full_name="Max Mustermann",
            email="nl@example.com",
            hourly_rate_60=Decimal("80.00"),
            cancellation_fee=Decimal("80.00"),
            practice=self.practice,
        )

        invoice = Invoice.objects.create(
            client=self.pat,
            invoice_number="NL-1",
            invoice_date=date.today() - timedelta(days=30),
            status="paid",
            total=Decimal("240.00"),
            practice=self.practice,
        )

        # Regular session billed at 80.00 — must NOT end up in no_log_needed
        self.regular_session = Session.objects.create(
            client=self.pat,
            session_date=date.today() - timedelta(days=20),
            duration=60,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.stype_regular,
            session=self.regular_session,
            rate=Decimal("80.00"),
            quantity=Decimal("1.00"),
            total=Decimal("80.00"),
        )

        # Cancellation session billed at 80.00 with Cancellation Fee type — MUST be in no_log_needed
        self.cancel_session = Session.objects.create(
            client=self.pat,
            session_date=date.today() - timedelta(days=10),
            duration=60,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.stype_cancel,
            session=self.cancel_session,
            rate=Decimal("80.00"),
            quantity=Decimal("1.00"),
            total=Decimal("80.00"),
        )

        # Explicitly cancelled session — must be in no_log_needed regardless of service type
        self.cancelled_session = Session.objects.create(
            client=self.pat,
            session_date=date.today() - timedelta(days=5),
            duration=60,
            cancelled=True,
        )

    def _get_no_log_ids(self):
        response = self.http.get(reverse("client_detail", kwargs={"pk": self.pat.pk}))
        self.assertEqual(response.status_code, 200)
        return response.context["no_log_needed_session_ids"]

    def test_regular_session_not_in_no_log_needed(self):
        """Regular session at same rate as cancellation_fee must NOT be suppressed."""
        ids = self._get_no_log_ids()
        self.assertNotIn(self.regular_session.pk, ids)

    def test_cancellation_fee_session_in_no_log_needed(self):
        """Session billed with 'Cancellation Fee' service type must be suppressed."""
        ids = self._get_no_log_ids()
        self.assertIn(self.cancel_session.pk, ids)

    def test_explicitly_cancelled_session_in_no_log_needed(self):
        """Session with cancelled=True must always be suppressed."""
        ids = self._get_no_log_ids()
        self.assertIn(self.cancelled_session.pk, ids)


class ClientCreateViewTest(TestCase):
    """Test client creation view."""

    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_client-3",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.client_instance = TestClient()
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance.login(username="testuser", password="testpass123")
        session = self.client_instance.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

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


class SessionLogDurationThresholdTest(TestCase):
    """
    Regression tests for the SESSION_LOG_MIN_DURATION threshold.

    Short sessions (duration <= SESSION_LOG_MIN_DURATION, typically intro calls
    imported from Google Calendar at ~20-30 min) must NOT cause the 📝 indicator
    on the client list.  Only sessions longer than the threshold need a log entry.
    """

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="log-duration-test",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="duruser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.http = TestClient()
        self.http.login(username="duruser", password="testpass123")
        session = self.http.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

        self.pat = Client.objects.create(
            client_code="DT1",
            full_name="Anna Schmidt",
            email="dur@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
            active=True,
        )

        # Place both sessions well within the window (5 days ago)
        self.recent_date = date.today() - timedelta(days=5)

    def _clients_needing_log(self):
        response = self.http.get(reverse("client_list"))
        self.assertEqual(response.status_code, 200)
        return response.context.get("clients_needing_log", set())

    def test_short_session_does_not_trigger_log_indicator(self):
        """A session at exactly SESSION_LOG_MIN_DURATION minutes must NOT flag the client."""
        Session.objects.create(
            client=self.pat,
            session_date=self.recent_date,
            duration=SESSION_LOG_MIN_DURATION,  # at threshold — should be excluded
            cancelled=False,
        )
        self.assertNotIn(self.pat.pk, self._clients_needing_log())

    def test_long_session_without_log_triggers_indicator(self):
        """A session longer than SESSION_LOG_MIN_DURATION with no log must flag the client."""
        Session.objects.create(
            client=self.pat,
            session_date=self.recent_date,
            duration=SESSION_LOG_MIN_DURATION + 1,  # just above threshold
            cancelled=False,
        )
        self.assertIn(self.pat.pk, self._clients_needing_log())

    def test_short_session_below_threshold_does_not_trigger(self):
        """A session well below the threshold (e.g. 20 min) must NOT flag the client."""
        Session.objects.create(
            client=self.pat,
            session_date=self.recent_date,
            duration=20,
            cancelled=False,
        )
        self.assertNotIn(self.pat.pk, self._clients_needing_log())


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
        session = self.client_browser.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

    def _get(self, name=""):
        return self.client_browser.get(reverse("suggest_client_code"), {"name": name})

    def test_empty_name_returns_empty(self):
        resp = self._get("")
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
