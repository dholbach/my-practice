"""
Tests for WeeklyFocusWidgetBuilder (P-028), specifically the "due today or
overdue" task list — merged onto due_date instead of the retired is_focus
flag so it shares one signal with the Focus Queue (P-050).
"""

from datetime import date, timedelta

from django.test import TestCase

from ..models import Practice, PracticeTodo
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
