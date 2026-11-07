"""Tests for the brute-force limit on sign-in, sign-out, and the idle session timeout."""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from ..models import LoginThrottle, TwoFactorDevice
from ..utils.login_throttle import failure_count, record_failure
from ..utils.two_factor import generate_secret
from ..views.auth_views import LOGIN_FAILURE_LIMIT
from .test_helpers import create_test_practice, link_user_to_practice


class LoginThrottleTests(TestCase):
    def setUp(self):
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

    def test_compatibility_spelling_does_not_bypass_the_limit(self):
        # "ｔｈｅｒａｐｉｓｔ" (fullwidth) NFKC-normalizes to "therapist", which is
        # the account Django's login form authenticates.
        fullwidth = "".join(chr(ord(c) + 0xFEE0) for c in "therapist")
        for _ in range(LOGIN_FAILURE_LIMIT):
            self._attempt("wrong")

        response = self._attempt("testpass123", username=fullwidth)

        self.assertEqual(response.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)


class ThrottleStorageTests(TestCase):
    """Counters live in their own table, so nothing that empties the cache unlocks."""

    def setUp(self):
        User.objects.create_user(username="therapist", password="testpass123")
        self.url = reverse("login")

    def _attempt(self, password, username="therapist"):
        return self.client.post(self.url, {"username": username, "password": password})

    def test_lockout_survives_the_cache_being_emptied(self):
        # The database cache culls a third of its rows at 300 entries; a flood
        # of junk usernames used to evict the target's counter that way.
        for _ in range(LOGIN_FAILURE_LIMIT):
            self._attempt("wrong")
        cache.clear()

        self.assertEqual(self._attempt("testpass123").status_code, 429)

    def test_lockout_ends_with_its_window(self):
        for _ in range(LOGIN_FAILURE_LIMIT):
            self._attempt("wrong")
        LoginThrottle.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

        self.assertEqual(self._attempt("testpass123").status_code, 302)

    def test_failure_after_the_window_starts_a_new_count(self):
        record_failure("k" * 64, 60)
        record_failure("k" * 64, 60)
        LoginThrottle.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

        self.assertEqual(record_failure("k" * 64, 60), 1)

    def test_expired_rows_are_purged_on_the_next_failure(self):
        record_failure("a" * 64, 60)
        LoginThrottle.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

        record_failure("b" * 64, 60)

        self.assertEqual(list(LoginThrottle.objects.values_list("key", flat=True)), ["b" * 64])
        self.assertEqual(failure_count("a" * 64), 0)

    def test_unknown_username_locks_like_a_real_one(self):
        # Same responses either way, so the lockout does not reveal which
        # usernames exist.
        for _ in range(LOGIN_FAILURE_LIMIT):
            self.assertEqual(self._attempt("wrong", username="nobody").status_code, 200)
        self.assertEqual(self._attempt("wrong", username="nobody").status_code, 429)

    def test_table_holds_no_usernames(self):
        self._attempt("wrong")
        key = LoginThrottle.objects.get().key
        self.assertNotIn("therapist", key)
        self.assertEqual(len(key), 64)


class ConcurrentAttemptTests(TestCase):
    """Each attempt row-locks the account it targets before reading the count.

    Reading the counter and checking the password are separate steps, so
    without a lock serialising one account's attempts, requests arriving together each read a count below
    the limit and each get a guess.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="therapist", password="testpass123")

    def _locked_tables(self, queries):
        return [q["sql"] for q in queries if "FOR UPDATE" in q["sql"]]

    def test_password_step_locks_the_account(self):
        with CaptureQueriesContext(connection) as queries:
            self.client.post(reverse("login"), {"username": "Therapist", "password": "wrong"})
        self.assertTrue(
            any('"auth_user"' in sql for sql in self._locked_tables(queries)),
            queries.captured_queries,
        )

    def test_code_step_locks_the_device(self):
        TwoFactorDevice.objects.create(
            user=self.user, secret=generate_secret(), confirmed_at="2026-01-01T00:00:00Z"
        )
        self.client.post(reverse("login"), {"username": "therapist", "password": "testpass123"})
        with CaptureQueriesContext(connection) as queries:
            self.client.post(reverse("login_verify"), {"code": "000000"})
        self.assertTrue(
            any("twofactordevice" in sql for sql in self._locked_tables(queries)),
            queries.captured_queries,
        )


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


class SignOutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="therapist", password="testpass123")
        self.client.login(username="therapist", password="testpass123")

    def test_every_page_offers_sign_out_and_it_signs_out(self):
        link_user_to_practice(self.user, create_test_practice())
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, f'action="{reverse("logout")}" method="post"')

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_user_without_a_practice_can_still_sign_out(self):
        # Such a user is sent to practice creation; it must not be a dead end.
        response = self.client.get(reverse("dashboard"), follow=True)
        self.assertEqual(response.redirect_chain[-1][0], reverse("practice_create"))
        self.assertContains(response, f'action="{reverse("logout")}" method="post"')
