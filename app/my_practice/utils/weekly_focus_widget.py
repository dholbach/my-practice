"""
Weekly Focus Widget for dashboard – shows Mon–Sun sessions plus tasks due
today or overdue. Part of P-028 Dashboard Redesign; the task half now shares
its "due today" signal with the Focus Queue (P-050) instead of the retired
is_focus flag — see docs/projects/done/P-028_DASHBOARD_WEEKLY_FOCUS.md.
"""

from datetime import date, timedelta

from django.db.models import QuerySet
from django.utils import timezone

from ..models import PracticeTodo, Session


class WeeklyFocusWidgetBuilder:
    """
    Builds context for the "Diese Woche" widget on the dashboard.

    Combines:
    - All sessions scheduled for the current calendar week (Mon–Sun), or for
      next week once today is past the current week's last session
    - All incomplete tasks due today or overdue (due_date <= today)

    Usage:
        builder = WeeklyFocusWidgetBuilder(practice)
        context = builder.build_context()
    """

    def __init__(self, practice, today: date | None = None):
        self.practice = practice
        self.today = today or timezone.localdate()
        # Monday and Sunday of current week
        self.week_start = self.today - timedelta(days=self.today.weekday())
        self.week_end = self.week_start + timedelta(days=6)
        self.is_next_week = False

    def _week_sessions_qs(self, start: date, end: date) -> QuerySet:
        return (
            Session.objects.filter(
                client__practice=self.practice,
                session_date__gte=start,
                session_date__lte=end,
                cancelled=False,
            )
            .select_related("client")
            .order_by("session_date", "session_time")
        )

    def _get_week_sessions(self) -> list[dict]:
        """Get non-cancelled sessions for this week, or next week once this one is over."""
        sessions = list(self._week_sessions_qs(self.week_start, self.week_end))
        if sessions and sessions[-1].session_date < self.today:
            # Nothing left this week; look ahead instead of listing only past sessions.
            self.is_next_week = True
            self.week_start += timedelta(days=7)
            self.week_end += timedelta(days=7)
            sessions = list(self._week_sessions_qs(self.week_start, self.week_end))
        return [
            {
                "date": s.session_date,
                "time": s.session_time,
                "client_code": s.client.client_code,
                "is_today": s.session_date == self.today,
                "is_past": s.session_date < self.today,
            }
            for s in sessions
        ]

    def _get_due_today_tasks(self) -> QuerySet:
        """Get incomplete tasks due today or overdue for the current practice."""
        return PracticeTodo.objects.filter(
            practice=self.practice,
            due_date__lte=self.today,
            completed_at__isnull=True,
        ).order_by("due_date", "-created_at")

    def build_context(self) -> dict:
        """
        Build and return widget context.

        Returns dict with:
            week_sessions: list of session dicts
            due_today_tasks: QuerySet of PracticeTodo
            is_next_week: bool, True when showing next week's sessions
            week_start: date (Monday)
            week_end: date (Sunday)
            session_count: int
            due_today_count: int
        """
        week_sessions = self._get_week_sessions()
        due_today_tasks = self._get_due_today_tasks()

        return {
            "week_sessions": week_sessions,
            "due_today_tasks": due_today_tasks,
            "is_next_week": self.is_next_week,
            "week_start": self.week_start,
            "week_end": self.week_end,
            "session_count": len(week_sessions),
            "due_today_count": due_today_tasks.count(),
            "today": self.today,
        }
