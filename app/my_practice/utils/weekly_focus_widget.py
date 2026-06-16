"""
Weekly Focus Widget for dashboard – shows Mon–Sun sessions plus focus tasks.
Part of P-028 Dashboard Redesign.
"""

from datetime import date, timedelta

from django.db.models import QuerySet

from ..models import PracticeTodo, Session


class WeeklyFocusWidgetBuilder:
    """
    Builds context for the "Diese Woche" widget on the dashboard.

    Combines:
    - All sessions scheduled for the current calendar week (Mon–Sun)
    - All incomplete focus tasks (is_focus=True)

    Usage:
        builder = WeeklyFocusWidgetBuilder(practice)
        context = builder.build_context()
    """

    def __init__(self, practice, today: date | None = None):
        self.practice = practice
        self.today = today or date.today()
        # Monday and Sunday of current week
        self.week_start = self.today - timedelta(days=self.today.weekday())
        self.week_end = self.week_start + timedelta(days=6)

    def _get_week_sessions(self) -> list[dict]:
        """Get all non-cancelled sessions for Mon–Sun of the current week."""
        sessions = (
            Session.objects.filter(
                client__practice=self.practice,
                session_date__gte=self.week_start,
                session_date__lte=self.week_end,
                cancelled=False,
            )
            .select_related("client")
            .order_by("session_date", "session_time")
        )
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

    def _get_focus_tasks(self) -> QuerySet:
        """Get active focus tasks for the current practice."""
        return PracticeTodo.objects.filter(
            practice=self.practice,
            is_focus=True,
            completed_at__isnull=True,
        ).order_by("due_date", "-created_at")

    def build_context(self) -> dict:
        """
        Build and return widget context.

        Returns dict with:
            week_sessions: list of session dicts
            focus_tasks: QuerySet of PracticeTodo
            week_start: date (Monday)
            week_end: date (Sunday)
            session_count: int
            focus_count: int
        """
        week_sessions = self._get_week_sessions()
        focus_tasks = self._get_focus_tasks()

        return {
            "week_sessions": week_sessions,
            "focus_tasks": focus_tasks,
            "week_start": self.week_start,
            "week_end": self.week_end,
            "session_count": len(week_sessions),
            "focus_count": focus_tasks.count(),
            "today": self.today,
            "todo_toggle_focus_url": "todo_toggle_focus",
        }
