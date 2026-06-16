"""
Custom email backend for Proton Bridge that accepts self-signed certificates.

Proton Bridge uses a self-signed certificate for STARTTLS on localhost:1025.
Standard Django SMTP backend rejects this, so we disable certificate verification.

Security Note: This is safe because:
1. Connection is to localhost only (no network exposure)
2. Proton Bridge itself handles the secure connection to Proton servers
3. We're just bypassing the local bridge certificate check
"""

import ssl

from django.core.mail.backends.smtp import EmailBackend as SMTPBackend


class ProtonBridgeEmailBackend(SMTPBackend):
    """
    Email backend that disables SSL certificate verification for localhost.

    This allows STARTTLS connections to Proton Bridge's self-signed certificate.
    Only use this for localhost connections to Proton Bridge!
    """

    def open(self):
        if self.connection:
            return False

        # Create SSL context that doesn't verify certificates
        # Safe for localhost-only connections to Proton Bridge
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        return super().open()
