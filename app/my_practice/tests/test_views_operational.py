"""
Tests for operational views (checklist and boilerplate).
"""

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import OperationalChecklistCompletion, Practice
from ..tests.test_helpers import link_user_to_practice


def _make_practice(slug):
    return Practice.objects.create(
        name="Ops Practice",
        slug=slug,
        title="Test Practitioner",
        email="ops@practice.example",
        city="Berlin",
    )


def _setup_client(user, practice=None):
    tc = TestClient()
    tc.login(username=user.username, password="testpass123")
    if practice:
        session = tc.session
        session["current_practice_slug"] = practice.slug
        session.save()
    return tc


class OperationalChecklistViewTest(TestCase):
    """Tests for OperationalChecklistView."""

    def setUp(self):
        self.practice = _make_practice("ops-checklist-1")
        self.user = User.objects.create_user(username="opsuser", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)

    def test_monthly_checklist_renders(self):
        response = self.tc.get(reverse("checklist", args=["monthly"]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/checklist.html")

    def test_weekly_checklist_renders(self):
        response = self.tc.get(reverse("checklist", args=["weekly"]))
        self.assertEqual(response.status_code, 200)

    def test_quarterly_checklist_renders(self):
        response = self.tc.get(reverse("checklist", args=["quarterly"]))
        self.assertEqual(response.status_code, 200)

    def test_annual_checklist_renders(self):
        response = self.tc.get(reverse("checklist", args=["annual"]))
        self.assertEqual(response.status_code, 200)

    def test_invalid_type_falls_back_to_monthly(self):
        response = self.tc.get(reverse("checklist", args=["bogustype"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["checklist_type"], "monthly")

    def test_items_in_context(self):
        response = self.tc.get(reverse("checklist", args=["monthly"]))
        self.assertIn("items", response.context)
        self.assertGreater(len(response.context["items"]), 0)

    def test_checklist_object_created(self):
        self.tc.get(reverse("checklist", args=["weekly"]))
        self.assertTrue(
            OperationalChecklistCompletion.objects.filter(checklist_type="weekly").exists()
        )


class ChecklistCompleteTest(TestCase):
    """Tests for checklist_complete view."""

    def setUp(self):
        self.practice = _make_practice("ops-complete-1")
        self.user = User.objects.create_user(username="opsuser2", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        # Ensure checklist exists by GETting it first
        self.tc.get(reverse("checklist", args=["weekly"]))

    def test_get_redirects_to_checklist(self):
        response = self.tc.get(reverse("checklist_complete", args=["weekly"]))
        self.assertEqual(response.status_code, 302)

    def test_post_marks_checklist_complete(self):
        response = self.tc.post(
            reverse("checklist_complete", args=["weekly"]), {"notes": "All done"}
        )
        self.assertEqual(response.status_code, 302)
        from ..views.operational_views import _get_period_start

        period_start = _get_period_start("weekly")
        checklist = OperationalChecklistCompletion.objects.get(
            checklist_type="weekly", year_month=period_start
        )
        self.assertTrue(checklist.is_completed)

    def test_post_unknown_type_redirects(self):
        response = self.tc.post(reverse("checklist_complete", args=["badtype"]))
        self.assertEqual(response.status_code, 302)


class ChecklistPauseItemTest(TestCase):
    """Tests for checklist_pause_item view."""

    def setUp(self):
        self.practice = _make_practice("ops-pause-1")
        self.user = User.objects.create_user(username="opsuser3", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)

    def test_post_pauses_item(self):
        response = self.tc.post(
            reverse("checklist_pause", args=["weekly", "run_backup"]),
            {"reason": "Laptop away", "paused_until": ""},
        )
        self.assertEqual(response.status_code, 302)
        from ..models import ChecklistItemPause

        self.assertTrue(
            ChecklistItemPause.objects.filter(
                checklist_type="weekly", item_id="run_backup"
            ).exists()
        )

    def test_post_invalid_item_redirects_with_message(self):
        response = self.tc.post(
            reverse("checklist_pause", args=["weekly", "nonexistent_item"]),
            {"reason": ""},
        )
        self.assertEqual(response.status_code, 302)


class ChecklistUnpauseItemTest(TestCase):
    """Tests for checklist_unpause_item view."""

    def setUp(self):
        self.practice = _make_practice("ops-unpause-1")
        self.user = User.objects.create_user(username="opsuser4", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        from ..models import ChecklistItemPause

        ChecklistItemPause.objects.create(checklist_type="monthly", item_id="restore_db")

    def test_post_removes_pause(self):
        response = self.tc.post(reverse("checklist_unpause", args=["monthly", "restore_db"]))
        self.assertEqual(response.status_code, 302)
        from ..models import ChecklistItemPause

        self.assertFalse(
            ChecklistItemPause.objects.filter(
                checklist_type="monthly", item_id="restore_db"
            ).exists()
        )


class BoilerplateViewTest(TestCase):
    """Tests for boilerplate_view."""

    def setUp(self):
        self.practice = _make_practice("ops-boilerplate-1")
        self.user = User.objects.create_user(username="opsuser5", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)

    def test_get_renders(self):
        response = self.tc.get(reverse("boilerplate"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/boilerplate.html")

    def test_cards_in_context(self):
        response = self.tc.get(reverse("boilerplate"))
        self.assertIn("cards", response.context)
        self.assertGreater(len(response.context["cards"]), 0)
