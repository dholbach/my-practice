"""
Custom encrypted field types for Art. 9 DSGVO (health data) protection.

Uses Fernet symmetric encryption from the `cryptography` library.
Key is read from settings.FERNET_KEY (set via FERNET_KEY env var).

Encrypted fields store Fernet ciphertext in the database — a plain SQL query
on an encrypted column returns `gAAAAA...` gibberish, never plaintext.

Limitations:
- Cannot use Django ORM filtering (.filter(), .exclude()) on encrypted values.
  Navigate clinical records via client + session_date + tags, not text search.
- Key rotation requires a data migration to re-encrypt all rows.
- Losing the key means losing access to all encrypted data. Back up the key.
"""

from django.conf import settings
from django.db import models


def _get_fernet():
    """Return a Fernet instance using settings.FERNET_KEY."""
    from cryptography.fernet import Fernet

    key = getattr(settings, "FERNET_KEY", None)
    if not key:
        raise RuntimeError(
            "FERNET_KEY is not set. Add it to your .env file. "
            'Generate one with: python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedTextField(models.TextField):
    """
    TextField that transparently encrypts/decrypts its value using Fernet.

    Stores ciphertext in the database; Python code sees plaintext strings.
    Empty strings and None are stored as-is (no encryption overhead for blank fields).
    """

    def from_db_value(self, value, _expression, connection):  # _expression: Django API requirement
        if value is None or value == "":
            return value
        return _get_fernet().decrypt(value.encode()).decode()

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return _get_fernet().encrypt(value.encode()).decode()


class EncryptedCharField(models.TextField):
    """
    CharField-equivalent that encrypts its value using Fernet.

    Stored as TextField in the database (Fernet ciphertext is ~100+ chars,
    max_length constraints on CharField are not meaningful post-encryption).
    """

    def from_db_value(self, value, _expression, connection):  # _expression: Django API requirement
        if value is None or value == "":
            return value
        return _get_fernet().decrypt(value.encode()).decode()

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return _get_fernet().encrypt(value.encode()).decode()
