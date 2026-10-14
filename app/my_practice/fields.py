"""
Custom encrypted field types for Art. 9 DSGVO (health data) protection.

Uses Fernet symmetric encryption from the `cryptography` library.
Keys are read from settings.FERNET_KEY (set via the FERNET_KEY env var).

Encrypted fields store Fernet ciphertext in the database — a plain SQL query
on an encrypted column returns `gAAAAA...` gibberish, never plaintext. That
also covers database dumps, so a leaked backup without the .env reveals nothing.

Key rotation: FERNET_KEY may hold several comma-separated keys. The first one
encrypts; every one of them decrypts. To rotate, put a new key in front, run
`manage.py encryption rotate` (re-encrypts every row under the new key), then
drop the old key. `manage.py encryption check` verifies the configured keys
open every stored value.

Limitations:
- Cannot use Django ORM filtering (.filter(), .exclude(), admin search,
  full-text search) on encrypted values. Navigate by client, date and tags.
- Losing every key means losing access to all encrypted data. Back up the key.
"""

from django.conf import settings
from django.db import models


class EncryptionKeyError(RuntimeError):
    """Stored ciphertext cannot be opened with any configured FERNET_KEY."""


def configured_keys() -> list[bytes]:
    """The keys in settings.FERNET_KEY, newest (encrypting) first."""
    raw = getattr(settings, "FERNET_KEY", None) or ""
    if isinstance(raw, bytes):
        raw = raw.decode()
    return [k.strip().encode() for k in raw.split(",") if k.strip()]


def get_fernet():
    """Return a MultiFernet over settings.FERNET_KEY (first key encrypts)."""
    from cryptography.fernet import Fernet, MultiFernet

    keys = configured_keys()
    if not keys:
        raise RuntimeError(
            "FERNET_KEY is not set. Add it to your .env file. "
            'Generate one with: python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return MultiFernet([Fernet(k) for k in keys])


def encrypt_value(value: str) -> str:
    """Encrypt a non-empty plaintext string with the current primary key."""
    return get_fernet().encrypt(value.encode()).decode()


def decrypt_value(value: str, label: str = "value") -> str:
    """Decrypt ciphertext, naming `label` in the error if no key opens it."""
    from cryptography.fernet import InvalidToken

    try:
        return get_fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        # Without this, the page dies on a bare InvalidToken that says nothing
        # about the cause: almost always a FERNET_KEY that differs from the
        # one the data was written with (a fresh .env, a restore onto a new
        # host). Never fall back to showing or re-saving the raw value — a
        # form saved over a placeholder would destroy the real data.
        raise EncryptionKeyError(
            f"Cannot decrypt {label}: no configured FERNET_KEY matches the key it was "
            "encrypted with. Restore the original FERNET_KEY in .env (keep it, "
            "comma-separated, after any newer key)."
        ) from None


class _EncryptedMixin:
    """Encrypts on the way into the database, decrypts on the way out."""

    def from_db_value(self, value, _expression, connection):  # _expression: Django API requirement
        if value is None or value == "":
            return value
        return decrypt_value(value, f"{self.model.__name__}.{self.name}")

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return encrypt_value(value)


class EncryptedTextField(_EncryptedMixin, models.TextField):
    """
    TextField that transparently encrypts/decrypts its value using Fernet.

    Stores ciphertext in the database; Python code sees plaintext strings.
    Empty strings and None are stored as-is (no encryption overhead for blank fields).
    """


class EncryptedCharField(_EncryptedMixin, models.TextField):
    """
    CharField-equivalent that encrypts its value using Fernet.

    Stored as TextField in the database (Fernet ciphertext is ~100+ chars,
    max_length constraints on CharField are not meaningful post-encryption).
    """


def encrypted_fields() -> list[tuple[type[models.Model], str]]:
    """Every (model, field name) pair stored encrypted, across installed apps."""
    from django.apps import apps

    return [
        (model, field.name)
        for model in apps.get_models()
        for field in model._meta.concrete_fields
        if isinstance(field, _EncryptedMixin)
    ]
