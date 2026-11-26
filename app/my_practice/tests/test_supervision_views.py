"""
Tests for the supervision views (P-009): create, toggle, resolve, delete and the queue.
"""

from datetime import date

from django.test import override_settings
from django.urls import reverse

from ..models import (
    Session,
    SupervisionItem,
)
from .test_clinical import TEST_FERNET_KEY, ClinicalTestBase


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

    def test_feedback_rendered_in_client_timeline(self):
        """Discussed supervision feedback appears in the Protocol timeline, dated
        by the day it was discussed, between the surrounding sessions."""
        Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 10), duration=60)
        Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 24), duration=60)
        SupervisionItem.objects.create(
            client=self.client_obj,
            content="Frage zur Abgrenzung",
            status=SupervisionItem.Status.BESPROCHEN,
            resolution_notes="Rat: Körperwahrnehmung stärker einbeziehen.",
            resolved_date=date(2026, 3, 17),
        )
        response = self.http.get(reverse("client_detail", kwargs={"pk": self.client_obj.pk}))
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        timeline = html[html.index('class="cn-session-list"') :]
        self.assertLess(timeline.index("24.03.2026"), timeline.index("Frage zur Abgrenzung"))
        self.assertLess(timeline.index("Frage zur Abgrenzung"), timeline.index("10.03.2026"))
        self.assertIn("Körperwahrnehmung stärker einbeziehen", timeline)

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
