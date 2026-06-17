from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase, override_settings

from my_practice.context_processors import _CACHE_KEY, update_check
from my_practice.version import VERSION


def _make_request(authenticated=True):
    factory = RequestFactory()
    request = factory.get("/")
    if authenticated:
        request.user = User(username="test", is_staff=True)
    else:
        request.user = AnonymousUser()
    return request


class UpdateCheckContextProcessorTest(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.delete(_CACHE_KEY)

    @override_settings(UPDATE_CHECK_DISABLED=True)
    def test_disabled_returns_empty(self):
        ctx = update_check(_make_request())
        self.assertEqual(ctx, {})

    @override_settings(DEBUG=True)
    def test_debug_mode_returns_empty(self):
        ctx = update_check(_make_request())
        self.assertEqual(ctx, {})

    def test_anonymous_user_returns_empty(self):
        ctx = update_check(_make_request(authenticated=False))
        self.assertEqual(ctx, {})

    def test_network_error_returns_empty(self):
        with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            ctx = update_check(_make_request())
        self.assertEqual(ctx, {})

    def test_already_on_latest_returns_empty(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                f'{{"tag_name": "{VERSION}"}}'.encode()
            )
            ctx = update_check(_make_request())
        self.assertEqual(ctx, {})

    def test_new_version_available(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                b'{"tag_name": "v99.0.0"}'
            )
            ctx = update_check(_make_request())
        self.assertTrue(ctx.get("update_available"))
        self.assertEqual(ctx.get("latest_version"), "v99.0.0")
        self.assertEqual(ctx.get("current_version"), VERSION)

    def test_result_is_cached(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                b'{"tag_name": "v99.0.0"}'
            )
            update_check(_make_request())
            update_check(_make_request())
        # GitHub should only be hit once; second call uses cache
        self.assertEqual(mock_open.call_count, 1)
