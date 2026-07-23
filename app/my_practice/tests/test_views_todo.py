"""
Tests for todo views.
"""

from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import Practice, PracticeTodo
from ..tests.test_helpers import link_user_to_practice

from django.contrib.auth.models import User


def _make_practice(slug):
    return Practice.objects.create(
        name="Test Practice",
        slug=slug,
        title="Test Practitioner",
        email="test@practice.example",
        city="Berlin",
    )


def _setup_client(user, practice):
    """Log in and set session practice slug. Returns TestClient."""
    tc = TestClient()
    tc.login(username=user.username, password="testpass123")
    session = tc.session
    session["current_practice_slug"] = practice.slug
    session.save()
    return tc


class TodoCreateViewTest(TestCase):
    """Tests for TodoCreateView."""

    def setUp(self):
        self.practice = _make_practice("todo-create-1")
        self.user = User.objects.create_user(username="todouser2", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)

    def test_get_renders(self):
        response = self.tc.get(reverse("todo_create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/todo_form.html")

    def test_post_valid_creates_todo(self):
        data = {"title": "New Todo", "category": "admin", "priority": "medium"}
        response = self.tc.post(reverse("todo_create"), data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PracticeTodo.objects.filter(title="New Todo").exists())

    def test_post_missing_title_stays_on_form(self):
        data = {"title": "", "category": "admin", "priority": "medium"}
        response = self.tc.post(reverse("todo_create"), data)
        self.assertEqual(response.status_code, 200)


class TodoUpdateViewTest(TestCase):
    """Tests for TodoUpdateView."""

    def setUp(self):
        self.practice = _make_practice("todo-update-1")
        self.user = User.objects.create_user(username="todouser3", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        self.todo = PracticeTodo.objects.create(
            practice=self.practice, title="Old Title", priority="low"
        )

    def test_get_renders_with_data(self):
        response = self.tc.get(reverse("todo_edit", args=[self.todo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Old Title")

    def test_post_valid_updates_todo(self):
        data = {"title": "Updated Title", "category": "admin", "priority": "high"}
        response = self.tc.post(reverse("todo_edit", args=[self.todo.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "Updated Title")

    def test_nonexistent_returns_404(self):
        response = self.tc.get(reverse("todo_edit", args=[99999]))
        self.assertEqual(response.status_code, 404)


class TodoDeleteViewTest(TestCase):
    """Tests for TodoDeleteView."""

    def setUp(self):
        self.practice = _make_practice("todo-delete-1")
        self.user = User.objects.create_user(username="todouser4", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        self.todo = PracticeTodo.objects.create(
            practice=self.practice, title="To Delete", priority="low"
        )

    def test_get_shows_confirmation(self):
        response = self.tc.get(reverse("todo_delete", args=[self.todo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "To Delete")

    def test_post_deletes_todo(self):
        pk = self.todo.pk
        response = self.tc.post(reverse("todo_delete", args=[pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PracticeTodo.objects.filter(pk=pk).exists())


class TodoToggleCompleteTest(TestCase):
    """Tests for todo_toggle_complete view."""

    def setUp(self):
        self.practice = _make_practice("todo-toggle-1")
        self.user = User.objects.create_user(username="todouser5", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        self.todo = PracticeTodo.objects.create(
            practice=self.practice, title="Toggle Me", priority="medium"
        )

    def test_non_htmx_redirects(self):
        response = self.tc.get(reverse("todo_toggle", args=[self.todo.pk]))
        self.assertEqual(response.status_code, 302)
        self.todo.refresh_from_db()
        self.assertTrue(self.todo.is_completed)

    def test_htmx_post_returns_content(self):
        response = self.tc.post(
            reverse("todo_toggle", args=[self.todo.pk]),
            HTTP_HX_REQUEST="true",
        )
        # HTMX response: either partial HTML or redirect
        self.assertIn(response.status_code, [200, 302])


class TodoToggleFocusTest(TestCase):
    """Tests for todo_toggle_focus view."""

    def setUp(self):
        self.practice = _make_practice("todo-focus-1")
        self.user = User.objects.create_user(username="todouser6", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        self.todo = PracticeTodo.objects.create(
            practice=self.practice, title="Focus Me", priority="medium", is_focus=False
        )

    def test_non_htmx_redirects(self):
        response = self.tc.post(reverse("todo_toggle_focus", args=[self.todo.pk]))
        self.assertEqual(response.status_code, 302)
        self.todo.refresh_from_db()
        self.assertTrue(self.todo.is_focus)

    def test_htmx_post_returns_200(self):
        response = self.tc.post(
            reverse("todo_toggle_focus", args=[self.todo.pk]),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)

    def test_nonexistent_returns_404(self):
        response = self.tc.post(reverse("todo_toggle_focus", args=[99999]))
        self.assertEqual(response.status_code, 404)
