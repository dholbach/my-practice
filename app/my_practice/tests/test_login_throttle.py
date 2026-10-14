"""Tests for the brute-force limit on sign-in and the idle session timeout."""

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from ..views.auth_views import LOGIN_FAILURE_LIMIT


class LoginThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        User.objects.create_user(username="therapist", password="testpass123")
        self.url = reverse("login")

    def _attempt(self, password, username="therapist"):
        return self.client.post(self.url, {"username": username, "password": password})

    def test_login_url_is_the_throttled_view(self):
        self.assertEqual(self.url, "/accounts/login/")
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_correct_password_signs_in(self):
        response = self._attempt("testpass123")
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_locked_after_limit_even_with_correct_password(self):
        for _ in range(LOGIN_FAILURE_LIMIT):
            self.assertEqual(self._attempt("wrong").status_code, 200)

        response = self._attempt("testpass123")

        self.assertEqual(response.status_code, 429)
        self.assertTrue(response.context["login_locked"])
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_success_before_limit_resets_the_count(self):
        for _ in range(LOGIN_FAILURE_LIMIT - 1):
            self._attempt("wrong")
        self.assertEqual(self._attempt("testpass123").status_code, 302)
        self.client.logout()

        for _ in range(LOGIN_FAILURE_LIMIT - 1):
            self._attempt("wrong")
        self.assertEqual(self._attempt("testpass123").status_code, 302)

    def test_lockout_is_per_username(self):
        User.objects.create_user(username="colleague", password="testpass456")
        for _ in range(LOGIN_FAILURE_LIMIT):
            self._attempt("wrong")

        self.assertEqual(self._attempt("testpass456", username="colleague").status_code, 302)

    def test_username_case_does_not_bypass_the_limit(self):
        for _ in range(LOGIN_FAILURE_LIMIT):
            self._attempt("wrong", username="Therapist")
        self.assertEqual(self._attempt("testpass123").status_code, 429)


class SessionIdleTimeoutTests(TestCase):
    def test_session_expires_after_idle_hours_not_two_weeks(self):
        self.assertEqual(settings.SESSION_COOKIE_AGE, 8 * 3600)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)

    def test_each_request_renews_the_session_cookie(self):
        User.objects.create_user(username="therapist", password="testpass123")
        self.client.login(username="therapist", password="testpass123")

        response = self.client.get(reverse("dashboard"))

        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertEqual(int(cookie["max-age"]), 8 * 3600)
