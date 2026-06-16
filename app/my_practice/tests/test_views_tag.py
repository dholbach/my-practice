"""
Tests for tag views.
"""

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import Client, ClientTag, Practice
from ..tests.test_helpers import link_user_to_practice
from decimal import Decimal


def _make_practice(slug):
    return Practice.objects.create(
        name="Tag Practice",
        slug=slug,
        title="Test Practitioner",
        email="tags@practice.example",
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


class TagListViewTest(TestCase):
    """Tests for TagListView."""

    def setUp(self):
        self.practice = _make_practice("tag-list-1")
        self.user = User.objects.create_user(username="taguser", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        ClientTag.objects.create(name="follow-up", color="blue")
        ClientTag.objects.create(name="missing-docs", color="red")

    def test_get_renders(self):
        response = self.tc.get(reverse("tag_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/tag_list.html")

    def test_tags_shown(self):
        response = self.tc.get(reverse("tag_list"))
        names = [t.name for t in response.context["tags"]]
        self.assertIn("follow-up", names)
        self.assertIn("missing-docs", names)


class TagCreateViewTest(TestCase):
    """Tests for TagCreateView."""

    def setUp(self):
        self.practice = _make_practice("tag-create-1")
        self.user = User.objects.create_user(username="taguser2", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)

    def test_get_renders_form(self):
        response = self.tc.get(reverse("tag_create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/tag_form.html")

    def test_post_valid_creates_tag(self):
        data = {"name": "urgent-review", "color": "orange", "description": ""}
        response = self.tc.post(reverse("tag_create"), data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ClientTag.objects.filter(name="urgent-review").exists())

    def test_post_duplicate_name_fails(self):
        ClientTag.objects.create(name="existing-tag", color="blue")
        data = {"name": "existing-tag", "color": "green", "description": ""}
        response = self.tc.post(reverse("tag_create"), data)
        self.assertEqual(response.status_code, 200)  # Form error, stays on page


class TagUpdateViewTest(TestCase):
    """Tests for TagUpdateView."""

    def setUp(self):
        self.practice = _make_practice("tag-update-1")
        self.user = User.objects.create_user(username="taguser3", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        self.tag = ClientTag.objects.create(name="old-tag-name", color="blue")

    def test_get_renders_with_data(self):
        response = self.tc.get(reverse("tag_update", args=[self.tag.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "old-tag-name")

    def test_post_updates_tag(self):
        data = {"name": "new-tag-name", "color": "green", "description": "Updated"}
        response = self.tc.post(reverse("tag_update", args=[self.tag.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.tag.refresh_from_db()
        self.assertEqual(self.tag.name, "new-tag-name")


class TagDeleteViewTest(TestCase):
    """Tests for TagDeleteView."""

    def setUp(self):
        self.practice = _make_practice("tag-delete-1")
        self.user = User.objects.create_user(username="taguser4", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        self.tag = ClientTag.objects.create(name="to-delete-tag", color="gray")

    def test_get_shows_confirmation(self):
        response = self.tc.get(reverse("tag_delete", args=[self.tag.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_deletes_tag(self):
        pk = self.tag.pk
        response = self.tc.post(reverse("tag_delete", args=[pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ClientTag.objects.filter(pk=pk).exists())


class ClientAddRemoveTagTest(TestCase):
    """Tests for client_add_tag and client_remove_tag AJAX endpoints."""

    def setUp(self):
        self.practice = _make_practice("tag-api-1")
        self.user = User.objects.create_user(username="tagapi", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        self.client_obj = Client.objects.create(
            client_code="TG-1",
            full_name="Max Mustermann",
            email="max@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        self.tag = ClientTag.objects.create(name="api-test-tag", color="blue")

    def test_add_tag(self):
        response = self.tc.post(
            reverse("client_add_tag", args=[self.client_obj.pk]),
            {"tag_id": self.tag.pk},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn(self.tag, self.client_obj.tags.all())

    def test_add_tag_missing_id_returns_400(self):
        response = self.tc.post(reverse("client_add_tag", args=[self.client_obj.pk]), {})
        self.assertEqual(response.status_code, 400)

    def test_remove_tag(self):
        self.client_obj.tags.add(self.tag)
        response = self.tc.post(
            reverse("client_remove_tag", args=[self.client_obj.pk, self.tag.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.tag, self.client_obj.tags.all())


class GetAvailableTagsTest(TestCase):
    """Tests for get_available_tags AJAX endpoint."""

    def setUp(self):
        self.practice = _make_practice("tag-avail-1")
        self.user = User.objects.create_user(username="tagavail", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        self.tag = ClientTag.objects.create(name="available-tag", color="purple")

    def test_returns_tags_json(self):
        response = self.tc.get(reverse("get_available_tags"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("tags", data)
        names = [t["name"] for t in data["tags"]]
        self.assertIn("available-tag", names)
