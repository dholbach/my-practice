"""The shared login helpers of tests/test_helpers.py, which a dozen view tests depend on."""

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from .test_helpers import (
    create_test_practice,
    link_user_to_practice,
    login_to_practice,
    select_practice,
)


class LoginHelperTests(TestCase):
    def setUp(self):
        self.practice = create_test_practice(slug="login-helpers-1")
        self.user = User.objects.create_user(username="helperuser", password="testpass123")
        link_user_to_practice(self.user, self.practice)

    def test_select_practice_sets_the_session_slug(self):
        http = TestClient()
        http.login(username="helperuser", password="testpass123")
        select_practice(http, self.practice)
        self.assertEqual(http.session["current_practice_slug"], self.practice.slug)

    def test_login_to_practice_logs_in_and_selects_the_practice(self):
        http = login_to_practice(self.user, self.practice)
        self.assertEqual(http.session["_auth_user_id"], str(self.user.pk))
        self.assertEqual(http.session["current_practice_slug"], self.practice.slug)
        self.assertEqual(http.get(reverse("expense_list")).status_code, 200)

    def test_login_to_practice_without_a_practice_leaves_the_slug_unset(self):
        http = login_to_practice(self.user)
        self.assertEqual(http.session["_auth_user_id"], str(self.user.pk))
        self.assertNotIn("current_practice_slug", http.session)

    def test_login_to_practice_takes_a_password(self):
        other = User.objects.create_user(username="otheruser", password="another-pass")
        link_user_to_practice(other, self.practice)
        http = login_to_practice(other, self.practice, password="another-pass")
        self.assertEqual(http.session["_auth_user_id"], str(other.pk))
