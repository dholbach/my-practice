"""
Tests for WeeklyFocusWidgetBuilder (P-028), specifically the "due today or
overdue" task list — merged onto due_date instead of the retired is_focus
flag so it shares one signal with the Focus Queue (P-050).
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from ..models import Client, Practice, PracticeTodo, Session
from ..utils.weekly_focus_widget import WeeklyFocusWidgetBuilder


def _make_practice(slug):
    return Practice.objects.create(
        name="Test Practice",
        slug=slug,
        title="Test Practitioner",
        email="test@practice.example",
        city="Berlin",
    )


class WeeklyFocusWidgetDueTodayTasksTest(TestCase):
    def setUp(self):
        self.practice = _make_practice("weekly-focus-widget-1")
        self.today = date(2026, 7, 30)

    def _build(self):
        return WeeklyFocusWidgetBuilder(self.practice, today=self.today).build_context()

    def test_includes_task_due_today(self):
        PracticeTodo.objects.create(practice=self.practice, title="Due today", due_date=self.today)
        context = self._build()
        titles = [t.title for t in context["due_today_tasks"]]
        self.assertIn("Due today", titles)
        self.assertEqual(context["due_today_count"], 1)

    def test_includes_overdue_task(self):
        PracticeTodo.objects.create(
            practice=self.practice, title="Overdue", due_date=self.today - timedelta(days=3)
        )
        context = self._build()
        titles = [t.title for t in context["due_today_tasks"]]
        self.assertIn("Overdue", titles)

    def test_excludes_task_due_in_future(self):
        PracticeTodo.objects.create(
            practice=self.practice, title="Later", due_date=self.today + timedelta(days=1)
        )
        context = self._build()
        titles = [t.title for t in context["due_today_tasks"]]
        self.assertNotIn("Later", titles)

    def test_excludes_task_without_due_date(self):
        PracticeTodo.objects.create(practice=self.practice, title="No due date")
        context = self._build()
        titles = [t.title for t in context["due_today_tasks"]]
        self.assertNotIn("No due date", titles)

    def test_excludes_completed_task(self):
        task = PracticeTodo.objects.create(
            practice=self.practice, title="Done already", due_date=self.today
        )
        task.mark_completed()
        context = self._build()
        titles = [t.title for t in context["due_today_tasks"]]
        self.assertNotIn("Done already", titles)


class WeeklyFocusWidgetNextWeekTest(TestCase):
    """Once the current week's last session is behind us, look at next week."""

    def setUp(self):
        self.practice = _make_practice("weekly-focus-widget-2")
        self.client_obj = Client.objects.create(
            client_code="XX-1",
            full_name="Max Mustermann",
            email="mail@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        # Wed 2026-11-11 and Fri 2026-11-13 are this week; Tue 2026-11-17 is next.
        for d in (date(2026, 11, 11), date(2026, 11, 13), date(2026, 11, 17)):
            Session.objects.create(client=self.client_obj, session_date=d, duration=60)

    def _build(self, today):
        return WeeklyFocusWidgetBuilder(self.practice, today=today).build_context()

    def test_shows_this_week_while_sessions_remain(self):
        context = self._build(date(2026, 11, 13))
        self.assertFalse(context["is_next_week"])
        self.assertEqual(context["session_count"], 2)

    def test_switches_to_next_week_after_last_session(self):
        context = self._build(date(2026, 11, 14))
        self.assertTrue(context["is_next_week"])
        self.assertEqual(context["week_start"], date(2026, 11, 16))
        self.assertEqual([s["date"] for s in context["week_sessions"]], [date(2026, 11, 17)])

    def test_empty_week_stays_this_week(self):
        context = self._build(date(2026, 11, 23))
        self.assertFalse(context["is_next_week"])
        self.assertEqual(context["session_count"], 0)
