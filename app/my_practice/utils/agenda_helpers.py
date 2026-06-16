"""
Agenda widget for dashboard - combines sessions and tasks in timeline view.
Part of P-003 Workflow-Driven Dashboard Redesign.
"""

from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Literal

from django.db.models import Q, QuerySet

from ..models import PracticeTodo, Session


@dataclass
class AgendaItem:
    """
    Unified agenda item (session or task) for timeline rendering.

    Attributes:
        type: "session" or "task"
        time: Time of day (None for unscheduled tasks)
        title: Display text (e.g., "Session Marie K." or "TODO: Rechnung versenden")
        description: Additional details
        client_code: For sessions (e.g., "MK")
        priority: For tasks ("low", "medium", "high", "urgent")
        url: Link to detail view
        is_completed: For tasks
        action_url: Quick action URL (mark done, view invoice, etc.)
        action_label: Quick action button text
        due_date: For tasks with due dates
        due_status: "overdue", "today", "soon", or None
    """

    type: Literal["session", "task"]
    time: time | None
    title: str
    description: str
    client_code: str | None = None
    priority: str | None = None
    url: str | None = None
    is_completed: bool = False
    action_url: str | None = None
    action_label: str | None = None
    due_date: date | None = None
    due_status: str | None = None

    @property
    def time_display(self) -> str:
        """Format time for display (e.g., '09:00')"""
        if self.time:
            return self.time.strftime("%H:%M")
        return "Keine Uhrzeit"

    @property
    def sort_key(self) -> tuple:
        """
        Sort key for agenda items:
        1. Sessions by time (scheduled first, unscheduled last)
        2. Tasks by due date (overdue first, then today, then soon, then no due date)
        """
        if self.type == "session":
            # Sessions: sort by time (unscheduled last)
            if self.time is None:
                return (1, 1, date.max, time(23, 59))
            return (1, 0, date.today(), self.time)
        else:
            # Tasks: sort by due status and due date
            # Priority order: overdue (0), today (1), soon (2), no due date (3)
            if self.due_status == "overdue":
                return (0, 0, self.due_date or date.today(), time(0, 0))
            elif self.due_status == "today":
                return (0, 1, self.due_date or date.today(), time(0, 0))
            elif self.due_status == "soon":
                return (0, 2, self.due_date or date.max, time(0, 0))
            else:
                # No due date - sort last
                return (0, 3, date.max, time(0, 0))


class AgendaWidgetBuilder:
    """
    Builds context for the Agenda Widget on the dashboard.

    Combines sessions (Session objects) and tasks (PracticeTodos)
    into a unified timeline for the specified date.

    Usage:
        builder = AgendaWidgetBuilder(practice, target_date=date.today())
        context = builder.build_context()
        # context contains:
        #   - agenda_items: List[AgendaItem] sorted by time
        #   - session_count: int
        #   - task_count: int
        #   - unscheduled_count: int
        #   - target_date: date
    """

    def __init__(self, practice, target_date: date | None = None):
        """
        Initialize builder with practice and target date.

        Args:
            practice: Practice object (from request.current_practice)
            target_date: Date to show agenda for (default: today)
        """
        self.practice = practice
        self.target_date = target_date or date.today()

    def _get_sessions(self) -> QuerySet:
        """Get sessions for target date with client info."""
        return (
            Session.objects.filter(
                client__practice=self.practice,
                session_date=self.target_date,
                cancelled=False,
            )
            .select_related("client")
            .prefetch_related("invoice_items__service_type", "invoice_items__invoice")
            .order_by("session_time")
        )

    def _get_tasks(self) -> QuerySet:
        """
        Get incomplete tasks for display in agenda.

        Includes:
        - Tasks due today or earlier (overdue)
        - Tasks due in the next 7 days
        - Tasks without a due date
        """
        seven_days_out = self.target_date + timedelta(days=7)

        return (
            PracticeTodo.objects.filter(
                practice=self.practice,
                completed_at__isnull=True,  # Only incomplete tasks
            )
            .filter(Q(due_date__lte=seven_days_out) | Q(due_date__isnull=True))
            .order_by("due_date")
        )  # Pre-sort by due date

    def _session_to_agenda_item(self, session: Session) -> AgendaItem:
        """Convert Session to AgendaItem."""
        client_code = session.client.client_code
        first_item = next(iter(session.invoice_items.all()), None)
        service_name = (
            first_item.service_type.name if first_item and first_item.service_type else "Sitzung"
        )
        description = f"{service_name} ({session.duration} Min.)"
        if first_item:
            url = f"/invoices/{first_item.invoice_id}/"
            action_label = "Rechnung anzeigen"
        else:
            url = f"/clients/{session.client_id}/detail/"
            action_label = "Klient anzeigen"
        return AgendaItem(
            type="session",
            time=session.session_time,
            title=f"Session {client_code}",
            description=description,
            client_code=client_code,
            url=url,
            action_url=url,
            action_label=action_label,
        )

    def _task_to_agenda_item(self, task: PracticeTodo) -> AgendaItem:
        """Convert PracticeTodo to AgendaItem"""
        # Tasks don't have time (for now - could be extended later)
        task_time = None

        # Title: "TODO: Rechnung versenden"
        title = f"TODO: {task.title}"

        # Calculate due status for highlighting
        due_status = None
        if task.due_date:
            days_until_due = (task.due_date - self.target_date).days
            if days_until_due < 0:
                due_status = "overdue"
            elif days_until_due == 0:
                due_status = "today"
            elif days_until_due <= 7:
                due_status = "soon"

        # Description: Category + priority + due date
        category_label = task.get_category_display()
        priority_label = task.get_priority_display()

        description_parts = [f"{category_label} • Priorität: {priority_label}"]
        if task.due_date:
            due_date_str = task.due_date.strftime("%d.%m.%Y")
            if due_status == "overdue":
                description_parts.append(f"⚠️ Überfällig seit {due_date_str}")
            elif due_status == "today":
                description_parts.append("📅 Heute fällig")
            elif due_status == "soon":
                days_until = (task.due_date - self.target_date).days
                description_parts.append(
                    f"📅 Fällig in {days_until} Tag{'en' if days_until != 1 else ''}"
                )

        description = " • ".join(description_parts)

        # URL to task edit page
        task_url = f"/todos/{task.id}/edit/" if hasattr(task, "id") else None

        # Action: Mark as done (toggle)
        action_url = f"/todos/{task.id}/toggle/" if hasattr(task, "id") else None

        return AgendaItem(
            type="task",
            time=task_time,
            title=title,
            description=description,
            priority=task.priority,
            url=task_url,
            is_completed=bool(task.completed_at),
            action_url=action_url,
            action_label="Erledigen",
            due_date=task.due_date,
            due_status=due_status,
        )

    def build_context(self) -> dict:
        """
        Build complete context for agenda widget.

        Returns:
            dict with:
                - agenda_items: List[AgendaItem] sorted by time
                - session_count: Number of sessions
                - task_count: Number of tasks
                - unscheduled_count: Number of items without time
                - target_date: Date being displayed
                - is_today: Whether target_date is today
        """
        # Get sessions and tasks
        sessions = self._get_sessions()
        tasks = self._get_tasks()

        # Convert to AgendaItems
        agenda_items = [self._session_to_agenda_item(session) for session in sessions]
        agenda_items.extend(self._task_to_agenda_item(task) for task in tasks)

        # Sort by time (unscheduled items last)
        agenda_items.sort(key=lambda item: item.sort_key)

        # Statistics
        session_count = len([item for item in agenda_items if item.type == "session"])
        task_count = len([item for item in agenda_items if item.type == "task"])
        unscheduled_count = len([item for item in agenda_items if item.time is None])

        return {
            "agenda_items": agenda_items,
            "session_count": session_count,
            "task_count": task_count,
            "unscheduled_count": unscheduled_count,
            "target_date": self.target_date,
            "is_today": self.target_date == date.today(),
        }
