"""Tests for PracticeTodo model"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from my_practice.models import Practice, PracticeTodo


class PracticeTodoModelTests(TestCase):
    """Test PracticeTodo model functionality"""

    def setUp(self):
        """Create test practice and todos"""
        self.practice = Practice.objects.create(
            name="Test Practice",
            title="Test Therapist",
        )

    def test_create_todo(self):
        """Test creating a basic TODO"""
        todo = PracticeTodo.objects.create(
            practice=self.practice,
            title="Get receipt for office supplies",
            category="admin",
            priority="medium",
        )
        self.assertEqual(todo.title, "Get receipt for office supplies")
        self.assertEqual(todo.category, "admin")
        self.assertEqual(todo.priority, "medium")
        self.assertFalse(todo.is_completed)

    def test_todo_str_representation(self):
        """Test string representation"""
        todo = PracticeTodo.objects.create(
            practice=self.practice,
            title="Book conference ticket",
        )
        self.assertIn("⏳", str(todo))
        self.assertIn("Book conference ticket", str(todo))

        todo.mark_completed()
        self.assertIn("✅", str(todo))

    def test_mark_completed(self):
        """Test marking TODO as completed"""
        todo = PracticeTodo.objects.create(
            practice=self.practice,
            title="Read research paper",
            category="learning",
        )
        self.assertIsNone(todo.completed_at)
        self.assertFalse(todo.is_completed)

        todo.mark_completed()
        self.assertIsNotNone(todo.completed_at)
        self.assertTrue(todo.is_completed)

    def test_mark_incomplete(self):
        """Test marking TODO as incomplete"""
        todo = PracticeTodo.objects.create(
            practice=self.practice,
            title="Update client records",
            completed_at=timezone.now(),
        )
        self.assertTrue(todo.is_completed)

        todo.mark_incomplete()
        self.assertIsNone(todo.completed_at)
        self.assertFalse(todo.is_completed)

    def test_is_overdue(self):
        """Test overdue detection"""
        # Past due date, not completed
        todo_overdue = PracticeTodo.objects.create(
            practice=self.practice,
            title="Overdue task",
            due_date=timezone.now().date() - timedelta(days=1),
        )
        self.assertTrue(todo_overdue.is_overdue)

        # Future due date
        todo_upcoming = PracticeTodo.objects.create(
            practice=self.practice,
            title="Upcoming task",
            due_date=timezone.now().date() + timedelta(days=7),
        )
        self.assertFalse(todo_upcoming.is_overdue)

        # Completed task (never overdue)
        todo_completed = PracticeTodo.objects.create(
            practice=self.practice,
            title="Completed task",
            due_date=timezone.now().date() - timedelta(days=7),
            completed_at=timezone.now(),
        )
        self.assertFalse(todo_completed.is_overdue)

        # No due date (never overdue)
        todo_no_date = PracticeTodo.objects.create(
            practice=self.practice,
            title="No due date",
        )
        self.assertFalse(todo_no_date.is_overdue)

    def test_practice_scoped_manager(self):
        """Test that todos are filtered by practice"""
        other_practice = Practice.objects.create(
            name="Other Practice",
            title="Other Therapist",
        )

        # Create todos for both practices
        todo1 = PracticeTodo.objects.create(
            practice=self.practice,
            title="Practice 1 TODO",
        )
        todo2 = PracticeTodo.objects.create(
            practice=other_practice,
            title="Practice 2 TODO",
        )

        # Test filtering
        practice1_todos = PracticeTodo.objects.for_practice(self.practice)
        self.assertEqual(practice1_todos.count(), 1)
        self.assertEqual(practice1_todos.first(), todo1)

        practice2_todos = PracticeTodo.objects.for_practice(other_practice)
        self.assertEqual(practice2_todos.count(), 1)
        self.assertEqual(practice2_todos.first(), todo2)

    def test_categories(self):
        """Test all TODO categories"""
        categories = ["admin", "learning", "financial", "client", "practice", "other"]
        for category in categories:
            todo = PracticeTodo.objects.create(
                practice=self.practice,
                title=f"Test {category} task",
                category=category,
            )
            self.assertEqual(todo.category, category)

    def test_priorities(self):
        """Test all priority levels"""
        priorities = ["low", "medium", "high", "urgent"]
        for priority in priorities:
            todo = PracticeTodo.objects.create(
                practice=self.practice,
                title=f"Test {priority} priority",
                priority=priority,
            )
            self.assertEqual(todo.priority, priority)

    def test_optional_fields(self):
        """Test optional description and due_date fields"""
        todo = PracticeTodo.objects.create(
            practice=self.practice,
            title="Minimal TODO",
        )
        self.assertEqual(todo.description, "")
        self.assertIsNone(todo.due_date)

        todo_full = PracticeTodo.objects.create(
            practice=self.practice,
            title="Full TODO",
            description="Detailed notes here",
            due_date=timezone.now().date() + timedelta(days=7),
        )
        self.assertEqual(todo_full.description, "Detailed notes here")
        self.assertIsNotNone(todo_full.due_date)

    def test_task_type_defaults_to_manual(self):
        """Existing/new plain TODOs default to task_type=manual (P-050)"""
        todo = PracticeTodo.objects.create(
            practice=self.practice,
            title="Plain manual task",
        )
        self.assertEqual(todo.task_type, PracticeTodo.TaskType.MANUAL)

    def test_task_types(self):
        """Test all task_type values are assignable"""
        for task_type in PracticeTodo.TaskType:
            todo = PracticeTodo.objects.create(
                practice=self.practice,
                title=f"Test {task_type} task",
                task_type=task_type,
            )
            self.assertEqual(todo.task_type, task_type)

    def test_is_snoozed(self):
        """Test snooze detection based on snoozed_until"""
        todo = PracticeTodo.objects.create(
            practice=self.practice,
            title="Snoozable task",
        )
        self.assertFalse(todo.is_snoozed)

        todo.snoozed_until = timezone.now().date() + timedelta(days=1)
        self.assertTrue(todo.is_snoozed)

        todo.snoozed_until = timezone.now().date() - timedelta(days=1)
        self.assertFalse(todo.is_snoozed)

    def test_related_object_generic_fk(self):
        """Test related_object links a materialized task back to its source"""
        other_practice = Practice.objects.create(
            name="Related Practice",
            title="Related Therapist",
        )
        todo = PracticeTodo.objects.create(
            practice=self.practice,
            title="Unpaid invoice follow-up",
            task_type=PracticeTodo.TaskType.INVOICE_UNPAID,
            related_object=other_practice,
        )
        todo.refresh_from_db()
        self.assertEqual(todo.related_object, other_practice)
