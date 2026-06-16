"""
Tests for P-009 clinical documentation models and views.

Covers:
  - Session model creation and constraints
  - ClientProfile get_or_create + Fernet field round-trip
  - SessionLog creation with mood_tags
  - SupervisionItem create + status toggle
  - clinical_views: client_profile_save, session_log_create, supervision_item_create,
    supervision_item_toggle, supervision_queue, client_triage_summary
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import (
    Client,
    ClientProfile,
    Practice,
    Session,
    SessionLog,
    SupervisionItem,
    UserPractice,
)

# ──────────────────────────────────────────────────────────────────────────────
# Use a deterministic test Fernet key so encrypted fields work in tests.
# Key must be a URL-safe base64-encoded 32-byte value.
# Generated once with: Fernet.generate_key().decode()
# ──────────────────────────────────────────────────────────────────────────────
TEST_FERNET_KEY = "7zIJPIlZkdMSPifNsPuNBjIAIqiUkFHmRJN8HGG8ytQ="  # gitleaks:allow


class ClinicalTestBase(TestCase):
    """Shared setUp for all clinical tests."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="clinical-test-1",
            title="Test Practitioner",
            email="test@practice.example",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="clinicaltestuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)

        self.client_obj = Client.objects.create(
            client_code="AB-1",
            full_name="Anna Schmidt",
            email="anna@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

        self.http = TestClient()
        self.http.login(username="clinicaltestuser", password="testpass123")


# ──────────────────────────────────────────────────────────────────────────────
# Model tests
# ──────────────────────────────────────────────────────────────────────────────


class SessionModelTests(ClinicalTestBase):
    """Tests for the Session central model."""

    def test_session_creation(self):
        """Session can be created with required fields."""
        s = Session.objects.create(
            client=self.client_obj,
            session_date=date(2026, 3, 15),
        )
        self.assertEqual(s.client, self.client_obj)
        self.assertEqual(s.duration, 60)  # default
        self.assertIsNone(s.session_time)

    def test_session_str(self):
        """Session __str__ returns client code + formatted date."""
        s = Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 15))
        self.assertIn("AB-1", str(s))
        self.assertIn("15.03.2026", str(s))

    def test_session_ordering(self):
        """Sessions are ordered by session_date descending."""
        s1 = Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 1))
        s2 = Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 15))
        sessions = list(Session.objects.filter(client=self.client_obj))
        self.assertEqual(sessions[0], s2)
        self.assertEqual(sessions[1], s1)

    def test_session_get_or_create(self):
        """get_or_create on same client+date returns existing session."""
        s1, created1 = Session.objects.get_or_create(
            client=self.client_obj, session_date=date(2026, 3, 15)
        )
        s2, created2 = Session.objects.get_or_create(
            client=self.client_obj, session_date=date(2026, 3, 15)
        )
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(s1.pk, s2.pk)


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class ClientProfileTests(ClinicalTestBase):
    """Tests for ClientProfile with Fernet-encrypted fields."""

    def test_profile_created_on_get_or_create(self):
        """ClientProfile can be created via get_or_create."""
        profile, created = ClientProfile.objects.get_or_create(client=self.client_obj)
        self.assertTrue(created)
        self.assertEqual(profile.client, self.client_obj)

    def test_encrypted_field_roundtrip(self):
        """Arbeitsdiagnose is encrypted at rest and decrypted on access."""
        profile = ClientProfile.objects.create(
            client=self.client_obj,
            arbeitsdiagnose="Depressive Episode (F32.1)",
            intake_notes="Erstgespräch verlief gut.",
        )
        # Reload from DB — should decrypt transparently
        fresh = ClientProfile.objects.get(pk=profile.pk)
        self.assertEqual(fresh.arbeitsdiagnose, "Depressive Episode (F32.1)")
        self.assertEqual(fresh.intake_notes, "Erstgespräch verlief gut.")

    def test_blank_encrypted_field_stays_blank(self):
        """Empty string encrypted fields remain empty after round-trip."""
        profile = ClientProfile.objects.create(client=self.client_obj, case_notes="")
        fresh = ClientProfile.objects.get(pk=profile.pk)
        self.assertEqual(fresh.case_notes, "")

    def test_one_profile_per_client(self):
        """Creating two profiles for the same client raises IntegrityError."""
        from django.db import IntegrityError

        ClientProfile.objects.create(client=self.client_obj)
        with self.assertRaises(IntegrityError):
            ClientProfile.objects.create(client=self.client_obj)


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class SessionLogTests(ClinicalTestBase):
    """Tests for SessionLog model."""

    def setUp(self):
        super().setUp()
        self.session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 15)
        )

    def test_session_log_creation(self):
        """SessionLog can be created linked to a Session."""
        log = SessionLog.objects.create(
            session=self.session,
            session_type="standard",
            mood_tags=["gute_ressourcen", "fortschritt"],
            content="Heutiger Fokus: Ressourcen.",
        )
        self.assertEqual(log.session, self.session)
        self.assertIn("gute_ressourcen", log.mood_tags)

    def test_mood_tags_unencrypted(self):
        """mood_tags are stored as plain JSON — not encrypted."""
        log = SessionLog.objects.create(
            session=self.session,
            mood_tags=["krise"],
        )
        fresh = SessionLog.objects.get(pk=log.pk)
        self.assertEqual(fresh.mood_tags, ["krise"])

    def test_one_log_per_session(self):
        """Creating two logs for the same session raises IntegrityError."""
        from django.db import IntegrityError

        SessionLog.objects.create(session=self.session)
        with self.assertRaises(IntegrityError):
            SessionLog.objects.create(session=self.session)

    def test_log_content_encrypted_roundtrip(self):
        """SessionLog content is encrypted at rest and decrypted on access."""
        log = SessionLog.objects.create(
            session=self.session,
            content="Sehr tiefes Gespräch über Kindheitserfahrungen.",
        )
        fresh = SessionLog.objects.get(pk=log.pk)
        self.assertEqual(fresh.content, "Sehr tiefes Gespräch über Kindheitserfahrungen.")


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class SupervisionItemTests(ClinicalTestBase):
    """Tests for SupervisionItem model."""

    def test_supervision_item_creation(self):
        """SupervisionItem can be created with default status 'offen'."""
        item = SupervisionItem.objects.create(
            client=self.client_obj,
            content="Wie gehe ich mit der Übertragung um?",
        )
        self.assertEqual(item.status, SupervisionItem.Status.OFFEN)
        self.assertEqual(item.client, self.client_obj)

    def test_supervision_item_toggle(self):
        """SupervisionItem status can be toggled between offen and besprochen."""
        item = SupervisionItem.objects.create(client=self.client_obj, content="Test")
        item.status = SupervisionItem.Status.BESPROCHEN
        item.save(update_fields=["status"])
        fresh = SupervisionItem.objects.get(pk=item.pk)
        self.assertEqual(fresh.status, SupervisionItem.Status.BESPROCHEN)

    def test_content_encrypted_roundtrip(self):
        """SupervisionItem content is encrypted at rest."""
        item = SupervisionItem.objects.create(
            client=self.client_obj,
            content="Gegenübertragungsthema: Ärger auf Klient.",
        )
        fresh = SupervisionItem.objects.get(pk=item.pk)
        self.assertEqual(fresh.content, "Gegenübertragungsthema: Ärger auf Klient.")


# ──────────────────────────────────────────────────────────────────────────────
# View tests
# ──────────────────────────────────────────────────────────────────────────────


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class ClientProfileSaveViewTests(ClinicalTestBase):
    """Tests for client_profile_save view."""

    def _url(self):
        return reverse("client_profile_save", kwargs={"pk": self.client_obj.pk})

    def test_save_creates_profile(self):
        """POST creates a new ClientProfile if none exists."""
        self.http.post(
            self._url(),
            {
                "arbeitsdiagnose": "F32.1",
                "intake_notes": "Erstgespräch gut.",
                "case_notes": "",
            },
        )
        self.assertTrue(ClientProfile.objects.filter(client=self.client_obj).exists())

    def test_save_updates_existing_profile(self):
        """POST updates an existing ClientProfile."""
        ClientProfile.objects.create(client=self.client_obj, arbeitsdiagnose="F32.0")
        self.http.post(
            self._url(),
            {
                "arbeitsdiagnose": "F33.0",
                "intake_notes": "",
                "case_notes": "",
            },
        )
        profile = ClientProfile.objects.get(client=self.client_obj)
        self.assertEqual(profile.arbeitsdiagnose, "F33.0")

    def test_get_not_allowed(self):
        """GET returns 405 Method Not Allowed."""
        response = self.http.get(self._url())
        self.assertEqual(response.status_code, 405)


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class SessionLogCreateViewTests(ClinicalTestBase):
    """Tests for session_log_create view."""

    def _url(self):
        return reverse("session_log_create", kwargs={"pk": self.client_obj.pk})

    def test_get_renders_form(self):
        """GET renders the session log form."""
        response = self.http.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/session_log_form.html")

    def test_post_creates_session_and_log(self):
        """POST creates a Session and SessionLog."""
        self.http.post(
            self._url(),
            {
                "session_date": "2026-03-20",
                "session_type": "standard",
                "mood_tags": ["gute_ressourcen"],
                "content": "Test content",
                "therapist_reflection": "",
            },
        )
        self.assertTrue(
            Session.objects.filter(client=self.client_obj, session_date=date(2026, 3, 20)).exists()
        )
        session = Session.objects.get(client=self.client_obj, session_date=date(2026, 3, 20))
        self.assertTrue(hasattr(session, "log"))
        self.assertEqual(session.log.mood_tags, ["gute_ressourcen"])

    def test_post_missing_date_redirects(self):
        """POST without session_date redirects with error."""
        response = self.http.post(
            self._url(),
            {
                "session_type": "standard",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Session.objects.filter(client=self.client_obj).exists())

    def test_post_finds_existing_session(self):
        """POST uses existing Session for the same client+date."""
        existing = Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 20))
        self.http.post(
            self._url(),
            {
                "session_date": "2026-03-20",
                "session_type": "standard",
                "mood_tags": [],
                "content": "",
            },
        )
        self.assertEqual(
            Session.objects.filter(client=self.client_obj, session_date=date(2026, 3, 20)).count(),
            1,
        )
        existing.refresh_from_db()
        self.assertTrue(hasattr(existing, "log"))


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class SupervisionViewTests(ClinicalTestBase):
    """Tests for supervision_item_create, supervision_item_toggle, supervision_queue."""

    def test_create_supervision_item(self):
        """POST to supervision_item_create creates an item."""
        url = reverse("supervision_item_create", kwargs={"pk": self.client_obj.pk})
        self.http.post(url, {"content": "Gesprächsdynamik klären"})
        self.assertTrue(SupervisionItem.objects.filter(client=self.client_obj).exists())

    def test_create_empty_content_rejected(self):
        """POST with blank content does not create an item."""
        url = reverse("supervision_item_create", kwargs={"pk": self.client_obj.pk})
        self.http.post(url, {"content": "   "})
        self.assertFalse(SupervisionItem.objects.filter(client=self.client_obj).exists())

    def test_toggle_supervision_item(self):
        """POST to supervision_item_toggle changes status."""
        item = SupervisionItem.objects.create(client=self.client_obj, content="Test")
        url = reverse(
            "supervision_item_toggle",
            kwargs={"pk": self.client_obj.pk, "item_pk": item.pk},
        )
        self.http.post(url)
        item.refresh_from_db()
        self.assertEqual(item.status, SupervisionItem.Status.BESPROCHEN)

    def test_toggle_ajax_returns_json(self):
        """AJAX POST to supervision_item_toggle returns JSON."""
        item = SupervisionItem.objects.create(client=self.client_obj, content="Test")
        url = reverse(
            "supervision_item_toggle",
            kwargs={"pk": self.client_obj.pk, "item_pk": item.pk},
        )
        response = self.http.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertEqual(data["status"], SupervisionItem.Status.BESPROCHEN)

    def test_supervision_queue_loads(self):
        """GET /supervision/ renders queue template."""
        SupervisionItem.objects.create(client=self.client_obj, content="Queue item")
        response = self.http.get(reverse("supervision_queue"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/supervision_queue.html")
        self.assertIn("grouped_items", response.context)

    def test_supervision_queue_shows_only_open(self):
        """Supervision queue only shows items with status=offen."""
        SupervisionItem.objects.create(
            client=self.client_obj, content="Open", status=SupervisionItem.Status.OFFEN
        )
        SupervisionItem.objects.create(
            client=self.client_obj, content="Done", status=SupervisionItem.Status.BESPROCHEN
        )
        response = self.http.get(reverse("supervision_queue"))
        total_open = response.context["total_open"]
        self.assertEqual(total_open, 1)


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class TriageSummaryViewTests(ClinicalTestBase):
    """Tests for client_triage_summary view."""

    def test_triage_loads(self):
        """GET /clients/triage/ renders the triage template."""
        response = self.http.get(reverse("client_triage"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/client_triage.html")

    def test_triage_uses_only_unencrypted_fields(self):
        """Triage context contains session_type and mood_tags (unencrypted), not content."""
        session = Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 20))
        SessionLog.objects.create(
            session=session,
            session_type="krisenintervention",
            mood_tags=["krise"],
            content="Encrypted content here",
        )
        response = self.http.get(reverse("client_triage"))
        self.assertEqual(response.status_code, 200)
        # Verify triage_data is in context
        self.assertIn("triage_data", response.context)
        entry = response.context["triage_data"][0]
        # Should expose unencrypted metadata
        sessions = entry["sessions"]
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_type"], "krisenintervention")
        self.assertIn("krise", sessions[0]["mood_tags"])
        # Encrypted 'content' field must NOT appear in session snapshots
        self.assertNotIn("content", sessions[0])
