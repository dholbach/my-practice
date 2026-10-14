import threading
import time
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase, override_settings

from my_practice.context_processors import (
    _CACHE_KEY,
    _LOCK_KEY,
    refresh_latest_release,
    update_check,
)
from my_practice.version import VERSION


def _make_request(authenticated=True):
    factory = RequestFactory()
    request = factory.get("/")
    if authenticated:
        request.user = User(username="test", is_staff=True)
    else:
        request.user = AnonymousUser()
    return request


def _check():
    """A cache-miss render (which starts the lookup), then the render that reads it."""
    update_check(_make_request())
    return update_check(_make_request())


class UpdateCheckContextProcessorTest(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.delete(_CACHE_KEY)
        cache.delete(_LOCK_KEY)
        # Run the lookup inline so each test sees its result deterministically.
        patcher = patch(
            "my_practice.context_processors._refresh_in_background", refresh_latest_release
        )
        patcher.start()
        self.addCleanup(patcher.stop)

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
            ctx = _check()
        self.assertEqual(ctx, {})

    def test_malformed_json_returns_empty(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = b"not json"
            ctx = _check()
        self.assertEqual(ctx, {})

    def test_failure_is_cached(self):
        """A failed lookup is not retried on the next request (only after 15 minutes)."""
        with patch("urllib.request.urlopen", side_effect=OSError("timeout")) as mock_open:
            update_check(_make_request())
            update_check(_make_request())
            ctx = update_check(_make_request())
        self.assertEqual(mock_open.call_count, 1)
        self.assertEqual(ctx, {})

    def test_already_on_latest_returns_empty(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                f'{{"tag_name": "{VERSION}"}}'.encode()
            )
            ctx = _check()
        self.assertEqual(ctx, {})

    def test_new_version_available(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                b'{"tag_name": "v99.0.0"}'
            )
            ctx = _check()
        self.assertTrue(ctx.get("update_available"))
        self.assertEqual(ctx.get("latest_version"), "v99.0.0")
        self.assertEqual(ctx.get("current_version"), VERSION)

    def test_older_release_is_not_offered_as_an_upgrade(self):
        """A version bump on main outruns its GitHub release; don't offer a downgrade."""
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                b'{"tag_name": "v0.0.1"}'
            )
            ctx = _check()
        self.assertEqual(ctx, {})

    def test_unparseable_tag_returns_empty(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                b'{"tag_name": "nightly"}'
            )
            ctx = _check()
        self.assertEqual(ctx, {})

    def test_patch_level_is_compared_numerically(self):
        """v0.10.0 is newer than v0.9.0 even though it sorts earlier as a string."""
        with (
            patch("my_practice.context_processors.VERSION", "v0.9.0"),
            patch("urllib.request.urlopen") as mock_open,
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = (
                b'{"tag_name": "v0.10.0"}'
            )
            ctx = _check()
        self.assertTrue(ctx.get("update_available"))
        self.assertEqual(ctx.get("latest_version"), "v0.10.0")

    def test_result_is_cached(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                b'{"tag_name": "v99.0.0"}'
            )
            update_check(_make_request())
            update_check(_make_request())
            update_check(_make_request())
        # GitHub should only be hit once; later calls use the cache
        self.assertEqual(mock_open.call_count, 1)


class UpdateCheckDoesNotBlockTest(TestCase):
    """The page render must not wait for GitHub, however slow it is."""

    def setUp(self):
        from django.core.cache import cache

        cache.delete(_CACHE_KEY)
        cache.delete(_LOCK_KEY)
        self.release = threading.Event()
        self.addCleanup(self.release.set)

    def _slow_urlopen(self, *args, **kwargs):
        self.release.wait(5)
        raise OSError("timeout")

    def test_render_returns_while_the_lookup_is_still_running(self):
        with patch("urllib.request.urlopen", side_effect=self._slow_urlopen) as mock_open:
            started = time.monotonic()
            ctx = update_check(_make_request())
            elapsed = time.monotonic() - started
            # A second render during the lookup does not start another one.
            update_check(_make_request())
            self.release.set()
            for thread in threading.enumerate():
                if thread.name == "update-check":
                    thread.join(5)
        self.assertEqual(ctx, {})
        self.assertLess(elapsed, 1)
        self.assertEqual(mock_open.call_count, 1)
