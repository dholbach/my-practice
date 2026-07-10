"""
Tests for the custom Proton Bridge email backend.
"""

import ssl
from unittest.mock import MagicMock, patch

from django.test import TestCase

from ..email_backend import ProtonBridgeEmailBackend


class ProtonBridgeEmailBackendTest(TestCase):
    def test_open_creates_permissive_ssl_context(self):
        backend = ProtonBridgeEmailBackend(fail_silently=True)
        with patch(
            "django.core.mail.backends.smtp.EmailBackend.open", return_value=True
        ) as mock_super_open:
            result = backend.open()

        self.assertTrue(result)
        mock_super_open.assert_called_once()
        self.assertFalse(backend.ssl_context.check_hostname)
        self.assertEqual(backend.ssl_context.verify_mode, ssl.CERT_NONE)

    def test_open_returns_false_when_already_connected(self):
        backend = ProtonBridgeEmailBackend(fail_silently=True)
        backend.connection = MagicMock()
        result = backend.open()
        self.assertFalse(result)
