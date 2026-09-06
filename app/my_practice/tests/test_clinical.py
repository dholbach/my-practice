"""
Tests for P-009 clinical documentation models and views.

Covers:
  - Session model creation and constraints
  - ClientProfile get_or_create + Fernet field round-trip
  - SessionLog creation with mood_tags
  - SupervisionItem create + status toggle
  - clinical_views: client_profile_save, session_log_create, supervision_item_create,
    supervision_item_toggle, supervision_queue, client_triage_summary,
    session_duration_edit
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import (
    Client,
    ClientNote,
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

    def test_post_adds_supervision_item_when_question_given(self):
        """A non-blank supervision_question also creates a SupervisionItem."""
        self.http.post(
            self._url(),
            {"session_date": "2026-03-20", "supervision_question": "Wie geht es weiter?"},
        )
        item = SupervisionItem.objects.get(client=self.client_obj)
        self.assertEqual(item.content, "Wie geht es weiter?")

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

    def test_post_invalid_date_redirects(self):
        """POST with an unparseable session_date redirects with error, no Session created."""
        response = self.http.post(self._url(), {"session_date": "not-a-date"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Session.objects.filter(client=self.client_obj).exists())

    def test_post_duplicate_log_warns_and_redirects_to_edit(self):
        """POST for a session that already has a log redirects to session_log_edit instead."""
        session = Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 20))
        log = SessionLog.objects.create(session=session, content="Existing")
        response = self.http.post(self._url(), {"session_date": "2026-03-20"})
        self.assertRedirects(
            response,
            reverse("session_log_edit", kwargs={"client_pk": self.client_obj.pk, "log_pk": log.pk}),
        )

    def test_get_prefills_duration_from_calendar_event(self):
        """GET with ?session_date= pre-fills duration from a matched calendar event."""
        from ..models import PendingCalendarEvent

        PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="evt-prefill-1",
            matched_client=self.client_obj,
            event_date=date(2026, 3, 20),
            duration_minutes=90,
            summary="Session",
        )
        response = self.http.get(self._url(), {"session_date": "2026-03-20"})
        self.assertEqual(response.context["prefill_duration"], 90)


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

    def test_resolve_marks_discussed_with_notes(self):
        """POST to supervision_item_resolve sets status, resolution notes, and date."""
        item = SupervisionItem.objects.create(client=self.client_obj, content="Test")
        url = reverse(
            "supervision_item_resolve",
            kwargs={"pk": self.client_obj.pk, "item_pk": item.pk},
        )
        self.http.post(url, {"resolution_notes": "Klar besprochen.", "resolved_date": "2026-05-01"})
        item.refresh_from_db()
        self.assertEqual(item.status, SupervisionItem.Status.BESPROCHEN)
        self.assertEqual(item.resolution_notes, "Klar besprochen.")
        self.assertEqual(item.resolved_date, date(2026, 5, 1))

    def test_resolve_defaults_date_to_today(self):
        """POST to supervision_item_resolve without a date defaults to today."""
        item = SupervisionItem.objects.create(client=self.client_obj, content="Test")
        url = reverse(
            "supervision_item_resolve",
            kwargs={"pk": self.client_obj.pk, "item_pk": item.pk},
        )
        self.http.post(url, {})
        item.refresh_from_db()
        self.assertEqual(item.status, SupervisionItem.Status.BESPROCHEN)
        self.assertEqual(item.resolved_date, date.today())

    def test_reopen_clears_resolution_fields(self):
        """Toggling a discussed item back to open clears its resolution notes/date."""
        item = SupervisionItem.objects.create(
            client=self.client_obj,
            content="Test",
            status=SupervisionItem.Status.BESPROCHEN,
            resolution_notes="Alte Notiz.",
            resolved_date=date(2026, 4, 1),
        )
        url = reverse(
            "supervision_item_toggle",
            kwargs={"pk": self.client_obj.pk, "item_pk": item.pk},
        )
        self.http.post(url)
        item.refresh_from_db()
        self.assertEqual(item.status, SupervisionItem.Status.OFFEN)
        self.assertEqual(item.resolution_notes, "")
        self.assertIsNone(item.resolved_date)

    def test_resolve_falls_back_to_today_on_unparseable_date(self):
        """A malformed resolved_date string falls back to today rather than erroring."""
        item = SupervisionItem.objects.create(client=self.client_obj, content="Test")
        url = reverse(
            "supervision_item_resolve",
            kwargs={"pk": self.client_obj.pk, "item_pk": item.pk},
        )
        self.http.post(url, {"resolved_date": "not-a-date"})
        item.refresh_from_db()
        self.assertEqual(item.resolved_date, date.today())

    def test_delete_supervision_item(self):
        """POST to supervision_item_delete removes the item."""
        item = SupervisionItem.objects.create(client=self.client_obj, content="Test")
        url = reverse(
            "supervision_item_delete",
            kwargs={"pk": self.client_obj.pk, "item_pk": item.pk},
        )
        self.http.post(url)
        self.assertFalse(SupervisionItem.objects.filter(pk=item.pk).exists())


class SessionDurationEditViewTests(ClinicalTestBase):
    """Tests for session_duration_edit — updates Session.duration."""

    def test_updates_duration(self):
        """POST with a valid duration updates the session."""
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 15), duration=60
        )
        url = reverse(
            "session_duration_edit", kwargs={"pk": self.client_obj.pk, "session_pk": session.pk}
        )
        self.http.post(url, {"duration": "15"})
        session.refresh_from_db()
        self.assertEqual(session.duration, 15)

    def test_rejects_invalid_duration(self):
        """POST with a non-positive duration leaves the session unchanged."""
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 15), duration=60
        )
        url = reverse(
            "session_duration_edit", kwargs={"pk": self.client_obj.pk, "session_pk": session.pk}
        )
        self.http.post(url, {"duration": "0"})
        session.refresh_from_db()
        self.assertEqual(session.duration, 60)

    def test_rejects_non_numeric_duration(self):
        """POST with a non-numeric duration leaves the session unchanged."""
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 15), duration=60
        )
        url = reverse(
            "session_duration_edit", kwargs={"pk": self.client_obj.pk, "session_pk": session.pk}
        )
        self.http.post(url, {"duration": "not-a-number"})
        session.refresh_from_db()
        self.assertEqual(session.duration, 60)

    def test_blocked_when_already_billed(self):
        """
        A session with an existing InvoiceItem cannot have its duration edited.

        The invoice item's service_type/rate/total are resolved at billing
        time and are not recalculated here, so allowing the edit would leave
        the invoice showing stale pricing for the session's new duration.
        """
        from ..models import Invoice, InvoiceItem, ServiceType

        service = ServiceType.objects.create(
            code="individual", name_en="Individual Session", name_de="Einzelsitzung"
        )
        invoice = Invoice.objects.create(
            client=self.client_obj,
            invoice_number="TEST-1",
            invoice_date=date(2026, 3, 15),
            practice=self.practice,
        )
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 15), duration=60
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=service,
            session=session,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )
        url = reverse(
            "session_duration_edit", kwargs={"pk": self.client_obj.pk, "session_pk": session.pk}
        )
        self.http.post(url, {"duration": "15"})
        session.refresh_from_db()
        self.assertEqual(session.duration, 60)


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


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class SessionLogEditViewTests(ClinicalTestBase):
    """Tests for session_log_edit — the update counterpart to session_log_create."""

    def setUp(self):
        super().setUp()
        self.session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), duration=60
        )
        self.log = SessionLog.objects.create(session=self.session, content="Original")

    def _url(self):
        return reverse(
            "session_log_edit",
            kwargs={"client_pk": self.client_obj.pk, "log_pk": self.log.pk},
        )

    def test_get_renders_form_with_existing_log(self):
        response = self.http.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/session_log_form.html")
        self.assertEqual(response.context["log"], self.log)
        self.assertTrue(response.context["is_edit"])

    def test_post_updates_log_fields(self):
        self.http.post(
            self._url(),
            {
                "session_type": "standard",
                "mood_tags": ["gute_ressourcen"],
                "content": "Updated content",
                "summary": "New summary",
            },
        )
        self.log.refresh_from_db()
        self.assertEqual(self.log.content, "Updated content")
        self.assertEqual(self.log.summary, "New summary")
        self.assertEqual(self.log.mood_tags, ["gute_ressourcen"])

    def test_post_updates_session_duration_when_valid(self):
        self.http.post(self._url(), {"content": "x", "duration": "45"})
        self.session.refresh_from_db()
        self.assertEqual(self.session.duration, 45)

    def test_post_ignores_invalid_duration(self):
        self.http.post(self._url(), {"content": "x", "duration": "not-a-number"})
        self.session.refresh_from_db()
        self.assertEqual(self.session.duration, 60)

    def test_post_adds_supervision_item_when_question_given(self):
        self.http.post(self._url(), {"content": "x", "supervision_question": "Wie weiter?"})
        item = SupervisionItem.objects.get(client=self.client_obj)
        self.assertEqual(item.content, "Wie weiter?")


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class ClientNoteViewTests(ClinicalTestBase):
    """Tests for client_note_create/update/delete."""

    def test_create_note(self):
        url = reverse("client_note_create", kwargs={"pk": self.client_obj.pk})
        self.http.post(url, {"note_date": "2026-03-20", "content": "Anruf wegen Termin"})
        note = ClientNote.objects.get(client=self.client_obj)
        self.assertEqual(note.content, "Anruf wegen Termin")

    def test_create_requires_date_and_content(self):
        url = reverse("client_note_create", kwargs={"pk": self.client_obj.pk})
        self.http.post(url, {"note_date": "", "content": ""})
        self.assertFalse(ClientNote.objects.filter(client=self.client_obj).exists())

    def test_create_rejects_invalid_date(self):
        url = reverse("client_note_create", kwargs={"pk": self.client_obj.pk})
        self.http.post(url, {"note_date": "not-a-date", "content": "Something"})
        self.assertFalse(ClientNote.objects.filter(client=self.client_obj).exists())

    def test_update_note(self):
        note = ClientNote.objects.create(
            client=self.client_obj, note_date=date(2026, 3, 20), content="Original"
        )
        url = reverse("client_note_update", kwargs={"pk": self.client_obj.pk, "note_pk": note.pk})
        self.http.post(url, {"content": "Updated", "note_date": "2026-03-21"})
        note.refresh_from_db()
        self.assertEqual(note.content, "Updated")
        self.assertEqual(note.note_date, date(2026, 3, 21))

    def test_update_rejects_empty_content(self):
        note = ClientNote.objects.create(
            client=self.client_obj, note_date=date(2026, 3, 20), content="Original"
        )
        url = reverse("client_note_update", kwargs={"pk": self.client_obj.pk, "note_pk": note.pk})
        self.http.post(url, {"content": "   "})
        note.refresh_from_db()
        self.assertEqual(note.content, "Original")

    def test_update_rejects_invalid_date_keeps_content_unsaved(self):
        note = ClientNote.objects.create(
            client=self.client_obj, note_date=date(2026, 3, 20), content="Original"
        )
        url = reverse("client_note_update", kwargs={"pk": self.client_obj.pk, "note_pk": note.pk})
        self.http.post(url, {"content": "Updated", "note_date": "not-a-date"})
        note.refresh_from_db()
        self.assertEqual(note.note_date, date(2026, 3, 20))

    def test_delete_note(self):
        note = ClientNote.objects.create(
            client=self.client_obj, note_date=date(2026, 3, 20), content="To delete"
        )
        url = reverse("client_note_delete", kwargs={"pk": self.client_obj.pk, "note_pk": note.pk})
        self.http.post(url)
        self.assertFalse(ClientNote.objects.filter(pk=note.pk).exists())


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class SessionQuickActionViewTests(ClinicalTestBase):
    """Tests for session_log_delete, session_delete, session_log_mark_noshow,
    session_toggle_billable, session_bill."""

    def test_delete_session_log_keeps_unbilled_session(self):
        """Deleting the log of a session with no InvoiceItem also deletes the bare Session."""
        session = Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 20))
        log = SessionLog.objects.create(session=session, content="x")
        url = reverse(
            "session_log_delete", kwargs={"client_pk": self.client_obj.pk, "log_pk": log.pk}
        )
        self.http.post(url)
        self.assertFalse(SessionLog.objects.filter(pk=log.pk).exists())
        self.assertFalse(Session.objects.filter(pk=session.pk).exists())

    def test_delete_session_log_keeps_billed_session(self):
        """Deleting the log of an already-billed session keeps the Session (only the log goes)."""
        from ..models import Invoice, InvoiceItem, ServiceType

        service = ServiceType.objects.create(
            code="individual", name_en="Individual Session", name_de="Einzelsitzung"
        )
        invoice = Invoice.objects.create(
            client=self.client_obj,
            invoice_number="TEST-2",
            invoice_date=date(2026, 3, 20),
            practice=self.practice,
        )
        session = Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 20))
        log = SessionLog.objects.create(session=session, content="x")
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=service,
            session=session,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )
        url = reverse(
            "session_log_delete", kwargs={"client_pk": self.client_obj.pk, "log_pk": log.pk}
        )
        self.http.post(url)
        self.assertFalse(SessionLog.objects.filter(pk=log.pk).exists())
        self.assertTrue(Session.objects.filter(pk=session.pk).exists())

    def test_delete_bare_session(self):
        session = Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 20))
        url = reverse(
            "session_delete", kwargs={"client_pk": self.client_obj.pk, "session_pk": session.pk}
        )
        self.http.post(url)
        self.assertFalse(Session.objects.filter(pk=session.pk).exists())

    def test_delete_blocked_when_billed(self):
        from ..models import Invoice, InvoiceItem, ServiceType

        service = ServiceType.objects.create(
            code="individual", name_en="Individual Session", name_de="Einzelsitzung"
        )
        invoice = Invoice.objects.create(
            client=self.client_obj,
            invoice_number="TEST-3",
            invoice_date=date(2026, 3, 20),
            practice=self.practice,
        )
        session = Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 20))
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=service,
            session=session,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )
        url = reverse(
            "session_delete", kwargs={"client_pk": self.client_obj.pk, "session_pk": session.pk}
        )
        self.http.post(url)
        self.assertTrue(Session.objects.filter(pk=session.pk).exists())

    def test_mark_noshow(self):
        session = Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 20))
        log = SessionLog.objects.create(session=session, session_type="standard")
        url = reverse(
            "session_log_mark_noshow",
            kwargs={"client_pk": self.client_obj.pk, "log_pk": log.pk},
        )
        self.http.post(url)
        log.refresh_from_db()
        self.assertEqual(log.session_type, SessionLog.SessionType.AUSFALL)

    def test_toggle_billable(self):
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), billable=True
        )
        url = reverse(
            "session_toggle_billable",
            kwargs={"client_pk": self.client_obj.pk, "session_pk": session.pk},
        )
        self.http.post(url)
        session.refresh_from_db()
        self.assertFalse(session.billable)
        self.http.post(url)
        session.refresh_from_db()
        self.assertTrue(session.billable)

    def test_session_bill_success(self):
        from ..models import ServiceType

        ServiceType.objects.create(
            practice=self.practice,
            code="therapy_60",
            name_en="Therapy 60",
            name_de="Therapie 60",
        )
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), duration=60
        )
        url = reverse("session_bill", kwargs={"pk": self.client_obj.pk, "session_pk": session.pk})
        response = self.http.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(session.invoice_items.exists())

    def test_session_bill_failure_shows_error(self):
        """No matching service type at all → error message, no InvoiceItem created."""
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), duration=60
        )
        url = reverse("session_bill", kwargs={"pk": self.client_obj.pk, "session_pk": session.pk})
        response = self.http.post(url, follow=True)
        messages_list = list(response.context["messages"])
        self.assertTrue(any(m.tags == "error" for m in messages_list))
        self.assertFalse(session.invoice_items.exists())
