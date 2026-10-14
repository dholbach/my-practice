"""Tests for two-factor sign-in (TOTP + recovery codes)."""

import base64
import time
from io import StringIO
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import RecoveryCode, TwoFactorDevice
from ..utils import two_factor
from ..utils.two_factor import current_step, generate_secret, new_recovery_codes, totp
from ..views.auth_views import LOGIN_FAILURE_LIMIT, PENDING_SECONDS
from .test_helpers import create_test_practice, link_user_to_practice

# RFC 6238 appendix B: the ASCII secret "12345678901234567890", SHA-1, 8 digits.
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()
RFC_VECTORS = [
    (59, "94287082"),
    (1111111109, "07081804"),
    (1111111111, "14050471"),
    (1234567890, "89005924"),
    (2000000000, "69279037"),
    (20000000000, "65353130"),
]


class TotpAlgorithmTests(TestCase):
    def test_rfc_6238_vectors(self):
        for timestamp, expected in RFC_VECTORS:
            with self.subTest(timestamp=timestamp):
                self.assertEqual(totp(RFC_SECRET, current_step(timestamp), digits=8), expected)

    def test_secret_is_160_bits_of_base32(self):
        secret = generate_secret()
        self.assertEqual(len(secret), 32)
        self.assertNotEqual(secret, generate_secret())


class TwoFactorTestBase(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user(username="therapist", password="testpass123")
        link_user_to_practice(self.user, create_test_practice())
        # Assertions below read English UI text; the default language is German.
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

    def _enable(self):
        device = TwoFactorDevice.objects.create(
            user=self.user, secret=generate_secret(), confirmed_at="2026-01-01T00:00:00Z"
        )
        return device, new_recovery_codes(device)

    def _code(self, device, offset_steps=0):
        return totp(device.secret, current_step() + offset_steps)

    def _password_step(self, next_url=""):
        url = reverse("login") + (f"?next={next_url}" if next_url else "")
        return self.client.post(url, {"username": "therapist", "password": "testpass123"})

    def _signed_in(self):
        return "_auth_user_id" in self.client.session


class SignInFlowTests(TwoFactorTestBase):
    def test_without_device_password_alone_signs_in(self):
        self.assertEqual(self._password_step().status_code, 302)
        self.assertTrue(self._signed_in())

    def test_password_alone_is_not_enough_with_device(self):
        self._enable()
        response = self._password_step()
        self.assertRedirects(response, reverse("login_verify"), fetch_redirect_response=False)
        self.assertFalse(self._signed_in())
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_valid_code_signs_in_and_honours_next(self):
        device, _codes = self._enable()
        self._password_step(next_url="/invoices/")
        response = self.client.post(reverse("login_verify"), {"code": self._code(device)})
        self.assertRedirects(response, "/invoices/", fetch_redirect_response=False)
        self.assertTrue(self._signed_in())

    def test_code_from_adjacent_step_is_accepted(self):
        device, _codes = self._enable()
        self._password_step()
        self.client.post(reverse("login_verify"), {"code": self._code(device, offset_steps=-1)})
        self.assertTrue(self._signed_in())

    def test_wrong_code_is_refused(self):
        device, _codes = self._enable()
        self._password_step()
        wrong = str((int(self._code(device)) + 1) % 1_000_000).zfill(6)
        response = self.client.post(reverse("login_verify"), {"code": wrong})
        self.assertContains(response, "not valid")
        self.assertFalse(self._signed_in())

    def test_code_cannot_be_replayed(self):
        device, _codes = self._enable()
        code = self._code(device)
        self._password_step()
        self.client.post(reverse("login_verify"), {"code": code})
        self.client.logout()

        self._password_step()
        self.client.post(reverse("login_verify"), {"code": code})
        self.assertFalse(self._signed_in())

    def test_recovery_code_works_once(self):
        _device, codes = self._enable()
        self._password_step()
        self.client.post(reverse("login_verify"), {"code": codes[0].lower()})
        self.assertTrue(self._signed_in())
        self.client.logout()

        self._password_step()
        self.client.post(reverse("login_verify"), {"code": codes[0]})
        self.assertFalse(self._signed_in())

    def test_recovery_codes_are_stored_hashed(self):
        _device, codes = self._enable()
        stored = set(RecoveryCode.objects.values_list("code_hash", flat=True))
        self.assertEqual(len(stored), 10)
        self.assertFalse(stored & set(codes))

    def test_code_attempts_are_limited(self):
        device, _codes = self._enable()
        self._password_step()
        for _attempt in range(LOGIN_FAILURE_LIMIT):
            self.client.post(reverse("login_verify"), {"code": "000000"})

        response = self.client.post(reverse("login_verify"), {"code": self._code(device)})

        self.assertEqual(response.status_code, 429)
        self.assertFalse(self._signed_in())

    def test_pending_password_step_expires(self):
        device, _codes = self._enable()
        self._password_step()
        later = time.time() + PENDING_SECONDS + 1
        with mock.patch("my_practice.views.auth_views.time.time", return_value=later):
            response = self.client.post(reverse("login_verify"), {"code": self._code(device)})
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertFalse(self._signed_in())

    def test_verify_page_without_password_step_goes_to_login(self):
        response = self.client.get(reverse("login_verify"))
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)

    def test_admin_login_goes_through_our_login(self):
        response = self.client.get("/admin/login/?next=/admin/")
        self.assertRedirects(
            response, reverse("login") + "?next=/admin/", fetch_redirect_response=False
        )
        response = self.client.post(
            "/admin/login/", {"username": "therapist", "password": "testpass123"}
        )
        self.assertFalse(self._signed_in())


class SettingsPageTests(TwoFactorTestBase):
    def setUp(self):
        super().setUp()
        self.client.login(username="therapist", password="testpass123")
        self.url = reverse("two_factor_settings")

    def test_setup_shows_qr_and_confirms_with_a_code(self):
        response = self.client.get(self.url)
        self.assertContains(response, "<svg")
        device = TwoFactorDevice.objects.get(user=self.user)
        self.assertFalse(device.is_confirmed)

        response = self.client.post(self.url, {"action": "confirm", "code": self._code(device)})

        device.refresh_from_db()
        self.assertTrue(device.is_confirmed)
        self.assertEqual(len(response.context["recovery_codes"]), 10)

    def test_wrong_code_does_not_confirm(self):
        self.client.get(self.url)
        self.client.post(self.url, {"action": "confirm", "code": "000000"})
        self.assertFalse(TwoFactorDevice.objects.get(user=self.user).is_confirmed)

    def test_disable_needs_password_and_code(self):
        device, codes = self._enable()
        self.client.post(self.url, {"action": "disable", "password": "wrong", "code": codes[0]})
        self.assertTrue(TwoFactorDevice.objects.filter(user=self.user).exists())
        # A wrong password must not burn the recovery code either.
        self.assertTrue(two_factor.use_recovery_code(device, codes[0]))

        self.client.post(
            self.url, {"action": "disable", "password": "testpass123", "code": self._code(device)}
        )
        self.assertFalse(TwoFactorDevice.objects.filter(user=self.user).exists())

    def test_regenerate_replaces_codes(self):
        device, old = self._enable()
        response = self.client.post(self.url, {"action": "regenerate", "code": self._code(device)})
        new = response.context["recovery_codes"]
        self.assertEqual(len(set(new) & set(old)), 0)
        self.assertFalse(two_factor.use_recovery_code(device, old[1]))

    def test_secret_is_encrypted_at_rest(self):
        device, _codes = self._enable()
        raw = TwoFactorDevice.objects.filter(pk=device.pk).values_list("secret", flat=True)
        # values_list goes through from_db_value; read the column directly.
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT secret FROM {TwoFactorDevice._meta.db_table} WHERE id = %s",  # noqa: S608
                [device.pk],
            )
            self.assertTrue(cursor.fetchone()[0].startswith("gAAAAA"))
        self.assertEqual(raw[0], device.secret)


@override_settings(REQUIRE_TWO_FACTOR=True)
class RequireTwoFactorTests(TwoFactorTestBase):
    def test_user_without_device_is_sent_to_setup(self):
        self.client.login(username="therapist", password="testpass123")
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(
            response, reverse("two_factor_settings"), fetch_redirect_response=False
        )
        self.assertContains(self.client.get(reverse("two_factor_settings")), "requires two-factor")

    def test_user_with_device_passes(self):
        device, _codes = self._enable()
        self._password_step()
        self.client.post(reverse("login_verify"), {"code": self._code(device)})
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)


class ResetCommandTests(TwoFactorTestBase):
    def test_reset_removes_device(self):
        self._enable()
        call_command("two_factor_reset", "therapist", stdout=StringIO())
        self.assertFalse(TwoFactorDevice.objects.filter(user=self.user).exists())
        self.assertEqual(self._password_step().status_code, 302)
        self.assertTrue(self._signed_in())
