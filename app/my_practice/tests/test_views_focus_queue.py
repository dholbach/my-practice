"""
Tests for Focus Queue views (P-050 phase 3).
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import Practice, PracticeTodo
from ..tests.test_helpers import link_user_to_practice


def _make_practice(slug):
    return Practice.objects.create(
        name="Test Practice",
        slug=slug,
        title="Test Practitioner",
        email="test@practice.example",
        city="Berlin",
    )


def _setup_client(user, practice):
    tc = TestClient()
    tc.login(username=user.username, password="testpass123")
    session = tc.session
    session["current_practice_slug"] = practice.slug
    session.save()
    return tc


class FocusQueueViewTest(TestCase):
    def setUp(self):
        self.practice = _make_practice("focus-queue-1")
        self.user = User.objects.create_user(username="fquser", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)

    def test_get_renders(self):
        response = self.tc.get(reverse("focus_queue"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/focus_queue.html")

    def test_shows_manual_and_materialized_tasks(self):
        PracticeTodo.objects.create(
            practice=self.practice, title="Manual task", task_type=PracticeTodo.TaskType.MANUAL
        )
        PracticeTodo.objects.create(
            practice=self.practice,
            title="XX-1",
            task_type=PracticeTodo.TaskType.MISSING_SESSION_LOG,
        )
        response = self.tc.get(reverse("focus_queue"))
        titles = [t.title for t in response.context["tasks"]]
        self.assertIn("Manual task", titles)
        self.assertIn("XX-1", titles)

    def test_excludes_completed(self):
        done = PracticeTodo.objects.create(practice=self.practice, title="Done")
        done.mark_completed()
        response = self.tc.get(reverse("focus_queue"))
        titles = [t.title for t in response.context["tasks"]]
        self.assertNotIn("Done", titles)

    def test_excludes_snoozed(self):
        PracticeTodo.objects.create(
            practice=self.practice,
            title="Snoozed",
            snoozed_until=timezone.now().date() + timedelta(days=1),
        )
        response = self.tc.get(reverse("focus_queue"))
        titles = [t.title for t in response.context["tasks"]]
        self.assertNotIn("Snoozed", titles)

    def test_includes_task_snoozed_in_the_past(self):
        PracticeTodo.objects.create(
            practice=self.practice,
            title="Past snooze",
            snoozed_until=timezone.now().date() - timedelta(days=1),
        )
        response = self.tc.get(reverse("focus_queue"))
        titles = [t.title for t in response.context["tasks"]]
        self.assertIn("Past snooze", titles)

    def test_ordered_by_priority_then_age(self):
        PracticeTodo.objects.create(practice=self.practice, title="Low", priority="low")
        PracticeTodo.objects.create(practice=self.practice, title="Urgent", priority="urgent")
        PracticeTodo.objects.create(practice=self.practice, title="Medium", priority="medium")
        response = self.tc.get(reverse("focus_queue"))
        titles = [t.title for t in response.context["tasks"]]
        self.assertEqual(titles, ["Urgent", "Medium", "Low"])

    def test_filter_by_type(self):
        PracticeTodo.objects.create(
            practice=self.practice, title="Manual", task_type=PracticeTodo.TaskType.MANUAL
        )
        PracticeTodo.objects.create(
            practice=self.practice,
            title="XX-1",
            task_type=PracticeTodo.TaskType.MISSING_SESSION_LOG,
        )
        response = self.tc.get(reverse("focus_queue") + "?type=missing_session_log")
        titles = [t.title for t in response.context["tasks"]]
        self.assertEqual(titles, ["XX-1"])

    def test_filter_by_type_empty_shows_all(self):
        PracticeTodo.objects.create(
            practice=self.practice, title="Manual", task_type=PracticeTodo.TaskType.MANUAL
        )
        PracticeTodo.objects.create(
            practice=self.practice,
            title="XX-1",
            task_type=PracticeTodo.TaskType.MISSING_SESSION_LOG,
        )
        response = self.tc.get(reverse("focus_queue"))
        titles = [t.title for t in response.context["tasks"]]
        self.assertEqual(set(titles), {"Manual", "XX-1"})

    def test_snoozed_count_respects_type_filter(self):
        PracticeTodo.objects.create(
            practice=self.practice,
            title="Snoozed manual",
            task_type=PracticeTodo.TaskType.MANUAL,
            snoozed_until=timezone.now().date() + timedelta(days=1),
        )
        PracticeTodo.objects.create(
            practice=self.practice,
            title="Snoozed invoice",
            task_type=PracticeTodo.TaskType.INVOICE_UNPAID,
            snoozed_until=timezone.now().date() + timedelta(days=1),
        )
        response = self.tc.get(reverse("focus_queue") + "?type=manual")
        self.assertEqual(response.context["snoozed_count"], 1)

    def test_snoozed_count_in_context(self):
        PracticeTodo.objects.create(
            practice=self.practice,
            title="Snoozed",
            snoozed_until=timezone.now().date() + timedelta(days=1),
        )
        response = self.tc.get(reverse("focus_queue"))
        self.assertEqual(response.context["snoozed_count"], 1)


class FocusQueueCompleteTest(TestCase):
    def setUp(self):
        self.practice = _make_practice("focus-queue-2")
        self.user = User.objects.create_user(username="fquser2", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        self.task = PracticeTodo.objects.create(practice=self.practice, title="To complete")

    def test_post_marks_completed(self):
        response = self.tc.post(reverse("focus_queue_complete", args=[self.task.pk]))
        self.assertEqual(response.status_code, 302)
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_completed)

    def test_htmx_returns_partial(self):
        response = self.tc.post(
            reverse("focus_queue_complete", args=[self.task.pk]), HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "includes/focus_queue_content.html")

    def test_htmx_partial_respects_type_filter_from_query_string(self):
        other = PracticeTodo.objects.create(
            practice=self.practice,
            title="Unpaid",
            task_type=PracticeTodo.TaskType.INVOICE_UNPAID,
        )
        response = self.tc.post(
            reverse("focus_queue_complete", args=[self.task.pk]) + "?type=invoice_unpaid",
            HTTP_HX_REQUEST="true",
        )
        titles = [t.title for t in response.context["tasks"]]
        self.assertEqual(titles, [other.title])

    def test_get_not_allowed(self):
        response = self.tc.get(reverse("focus_queue_complete", args=[self.task.pk]))
        self.assertEqual(response.status_code, 405)

    def test_cross_practice_404(self):
        other_practice = _make_practice("focus-queue-other")
        other_task = PracticeTodo.objects.create(practice=other_practice, title="Other")
        response = self.tc.post(reverse("focus_queue_complete", args=[other_task.pk]))
        self.assertEqual(response.status_code, 404)


class FocusQueueSnoozeTest(TestCase):
    def setUp(self):
        self.practice = _make_practice("focus-queue-3")
        self.user = User.objects.create_user(username="fquser3", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        self.task = PracticeTodo.objects.create(practice=self.practice, title="To snooze")

    def test_snooze_one_day(self):
        self.tc.post(reverse("focus_queue_snooze", args=[self.task.pk]), {"days": "1"})
        self.task.refresh_from_db()
        self.assertEqual(self.task.snoozed_until, timezone.now().date() + timedelta(days=1))

    def test_snooze_one_week(self):
        self.tc.post(reverse("focus_queue_snooze", args=[self.task.pk]), {"days": "7"})
        self.task.refresh_from_db()
        self.assertEqual(self.task.snoozed_until, timezone.now().date() + timedelta(days=7))

    def test_invalid_days_defaults_to_one(self):
        self.tc.post(reverse("focus_queue_snooze", args=[self.task.pk]), {"days": "bogus"})
        self.task.refresh_from_db()
        self.assertEqual(self.task.snoozed_until, timezone.now().date() + timedelta(days=1))

    def test_snoozed_task_disappears_from_queue(self):
        self.tc.post(reverse("focus_queue_snooze", args=[self.task.pk]), {"days": "3"})
        response = self.tc.get(reverse("focus_queue"))
        titles = [t.title for t in response.context["tasks"]]
        self.assertNotIn("To snooze", titles)
