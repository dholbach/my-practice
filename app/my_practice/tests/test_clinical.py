"""
Tests for P-009 clinical documentation models and views.

Covers:
  - Session model creation and constraints
  - ClientProfile get_or_create + Fernet field round-trip
  - SessionLog creation with mood_tags
  - SupervisionItem create + status toggle
  - clinical_views: session_log_create / session_log_edit, client notes, client_triage_summary
  (the supervision and one-session views are in test_supervision_views / test_session_views)
"""

from datetime import date, time
from decimal import Decimal

from django.test import Client as TestClient
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import (
    Client,
    ClientNote,
    ClientProfile,
    Session,
    SessionLog,
    SupervisionItem,
)
from .test_helpers import create_test_practice, create_test_user

# ──────────────────────────────────────────────────────────────────────────────
# Use a deterministic test Fernet key so encrypted fields work in tests.
# Key must be a URL-safe base64-encoded 32-byte value.
# Generated once with: Fernet.generate_key().decode()
# ──────────────────────────────────────────────────────────────────────────────
TEST_FERNET_KEY = "7zIJPIlZkdMSPifNsPuNBjIAIqiUkFHmRJN8HGG8ytQ="  # gitleaks:allow


class ClinicalTestBase(TestCase):
    """Shared setUp for all clinical tests."""

    def setUp(self):
        self.practice = create_test_practice(
            name="Test Practice", slug="clinical-test-1", email="test@practice.example"
        )
        self.user = create_test_user(
            self.practice, username="clinicaltestuser", password="testpass123"
        )

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

    def test_post_two_sessions_same_day_attaches_to_unlogged_one(self):
        """With two sessions on one date, the log goes to the one without a log yet."""
        logged = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), session_time=time(9, 0)
        )
        SessionLog.objects.create(session=logged, content="Morning")
        afternoon = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), session_time=time(15, 0)
        )
        response = self.http.post(self._url(), {"session_date": "2026-03-20", "content": "Later"})
        self.assertEqual(response.status_code, 302)
        afternoon.refresh_from_db()
        self.assertEqual(afternoon.log.content, "Later")
        self.assertEqual(Session.objects.filter(client=self.client_obj).count(), 2)

    def test_post_skips_cancelled_twin_left_by_reschedule(self):
        """A cancelled session at the same slot (reschedule leftover) is not chosen."""
        Session.objects.create(
            client=self.client_obj,
            session_date=date(2026, 3, 20),
            session_time=time(10, 0),
            cancelled=True,
        )
        live = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), session_time=time(10, 0)
        )
        self.http.post(self._url(), {"session_date": "2026-03-20", "content": "Notes"})
        live.refresh_from_db()
        self.assertEqual(live.log.content, "Notes")

    def test_post_logged_live_session_with_cancelled_twin_redirects_to_edit(self):
        """Once the live session is logged, its unlogged cancelled twin is not used."""
        Session.objects.create(
            client=self.client_obj,
            session_date=date(2026, 3, 20),
            session_time=time(10, 0),
            cancelled=True,
        )
        live = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), session_time=time(10, 0)
        )
        log = SessionLog.objects.create(session=live, content="Existing")
        response = self.http.post(self._url(), {"session_date": "2026-03-20"})
        self.assertRedirects(
            response,
            reverse("session_log_edit", kwargs={"client_pk": self.client_obj.pk, "log_pk": log.pk}),
        )

    def test_post_two_logged_sessions_same_day_redirects_to_edit(self):
        """If every session that day already has a log, redirect to editing the first."""
        first = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), session_time=time(9, 0)
        )
        second = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), session_time=time(15, 0)
        )
        first_log = SessionLog.objects.create(session=first, content="A")
        SessionLog.objects.create(session=second, content="B")
        response = self.http.post(self._url(), {"session_date": "2026-03-20"})
        self.assertRedirects(
            response,
            reverse(
                "session_log_edit", kwargs={"client_pk": self.client_obj.pk, "log_pk": first_log.pk}
            ),
        )

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

    def test_post_rejects_unusable_duration_without_creating_anything(self):
        """A non-numeric or overflowing duration is refused instead of raising a 500."""
        for duration in ("abc", "0", "99999999999"):
            with self.subTest(duration=duration):
                response = self.http.post(
                    self._url(),
                    {
                        "session_date": "2026-03-21",
                        "session_type": "standard",
                        "duration": duration,
                    },
                )
                self.assertRedirects(
                    response, reverse("client_detail", kwargs={"pk": self.client_obj.pk})
                )
                self.assertFalse(Session.objects.filter(client=self.client_obj).exists())

    def test_post_accepts_a_full_day_session(self):
        self.http.post(
            self._url(),
            {"session_date": "2026-03-21", "session_type": "standard", "duration": "480"},
        )
        self.assertEqual(Session.objects.get(client=self.client_obj).duration, 480)

    def test_post_rejects_unknown_session_type(self):
        self.http.post(
            self._url(), {"session_date": "2026-03-21", "session_type": "x" * 100, "content": "x"}
        )
        self.assertFalse(SessionLog.objects.filter(session__client=self.client_obj).exists())

    def test_post_drops_unknown_mood_tags(self):
        self.http.post(
            self._url(),
            {
                "session_date": "2026-03-21",
                "session_type": "standard",
                "mood_tags": ["gute_ressourcen", "<script>"],
            },
        )
        log = SessionLog.objects.get(session__client=self.client_obj)
        self.assertEqual(log.mood_tags, ["gute_ressourcen"])

    def test_get_ignores_invalid_prefill_date(self):
        response = self.http.get(self._url() + "?session_date=not-a-date")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["prefill_date"], "")


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

    def test_post_keeps_duration_of_billed_session_but_saves_log(self):
        """Billed figures depend on session.duration, so the log edit must not change it."""
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
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=service,
            session=self.session,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )
        self.http.post(self._url(), {"content": "Edited", "duration": "90"})
        self.session.refresh_from_db()
        self.log.refresh_from_db()
        self.assertEqual(self.session.duration, 60)
        self.assertEqual(self.log.content, "Edited")

    def test_post_keeps_session_type_when_unknown(self):
        self.log.session_type = SessionLog.SessionType.ERSTGESPRAECH
        self.log.save()
        self.http.post(self._url(), {"content": "x", "session_type": "bogus"})
        self.log.refresh_from_db()
        self.assertEqual(self.log.session_type, SessionLog.SessionType.ERSTGESPRAECH)
        self.assertEqual(self.log.content, "x")

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
