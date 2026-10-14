"""
TOTP (RFC 6238) for the second sign-in factor, and recovery codes.

Standard-library only: TOTP is HMAC-SHA1 over a 30-second counter, and every
authenticator app (Aegis, Google Authenticator, 1Password, …) speaks exactly
this default — 6 digits, 30 seconds, SHA-1. The implementation is checked
against the RFC's own test vectors in test_two_factor.py.
"""

import base64
import hashlib
import hmac
import io
import secrets
import struct
import time
from urllib.parse import quote, urlencode

import segno
from django.db import transaction
from django.utils import timezone

from ..models import RecoveryCode, TwoFactorDevice

STEP_SECONDS = 30
DIGITS = 6
# Accept the previous and next step too: phone clocks drift, and a code typed
# in the last seconds of its window arrives in the next one.
DRIFT_STEPS = 1
RECOVERY_CODE_COUNT = 10


def generate_secret() -> str:
    """A new random base32 secret (160 bits, the RFC 4226 recommendation)."""
    return base64.b32encode(secrets.token_bytes(20)).decode()


def totp(secret: str, step: int, digits: int = DIGITS) -> str:
    """The code for one time step (RFC 6238 / RFC 4226 dynamic truncation)."""
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**digits).zfill(digits)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // STEP_SECONDS)


def _normalise(code: str) -> str:
    return "".join(code.split()).replace("-", "").upper()


def verify_totp(device: TwoFactorDevice, code: str, now: float | None = None) -> bool:
    """Check a code and, if valid, record its step so it cannot be used again."""
    code = _normalise(code)
    if len(code) != DIGITS or not code.isdigit():
        return False
    here = current_step(now)
    with transaction.atomic():
        locked = TwoFactorDevice.objects.select_for_update().get(pk=device.pk)
        for step in range(here - DRIFT_STEPS, here + DRIFT_STEPS + 1):
            if step > locked.last_used_step and hmac.compare_digest(
                totp(locked.secret, step), code
            ):
                locked.last_used_step = step
                locked.save(update_fields=["last_used_step", "updated_at"])
                device.last_used_step = step
                return True
    return False


def provisioning_uri(secret: str, account: str, issuer: str) -> str:
    """The otpauth:// URI an authenticator app reads from the QR code."""
    label = quote(f"{issuer}:{account}")
    return f"otpauth://totp/{label}?" + urlencode({"secret": secret, "issuer": issuer})


def qr_svg(data: str) -> str:
    """An inline SVG QR code (no external request, no script — CSP-safe)."""
    buffer = io.BytesIO()
    segno.make(data, error="m").save(
        buffer,
        kind="svg",
        scale=5,
        border=2,
        xmldecl=False,
        svgns=True,
        dark="#1a202c",
        light="#ffffff",
    )
    return buffer.getvalue().decode()


def _hash_code(code: str) -> str:
    # Recovery codes carry 50 random bits, so a fast hash is enough: there is
    # no low-entropy space to brute-force as there is with passwords.
    return hashlib.sha256(_normalise(code).encode()).hexdigest()


def new_recovery_codes(device: TwoFactorDevice) -> list[str]:
    """Replace the device's recovery codes; return the plain codes (shown once)."""
    codes = []
    for _index in range(RECOVERY_CODE_COUNT):
        raw = base64.b32encode(secrets.token_bytes(10)).decode()[:10]
        codes.append(f"{raw[:5]}-{raw[5:]}")
    with transaction.atomic():
        device.recovery_codes.all().delete()
        RecoveryCode.objects.bulk_create(
            RecoveryCode(device=device, code_hash=_hash_code(code)) for code in codes
        )
    return codes


def use_recovery_code(device: TwoFactorDevice, code: str) -> bool:
    """Consume an unused recovery code; True if it was valid."""
    with transaction.atomic():
        match = (
            device.recovery_codes.select_for_update()
            .filter(code_hash=_hash_code(code), used_at__isnull=True)
            .first()
        )
        if match is None:
            return False
        match.used_at = timezone.now()
        match.save(update_fields=["used_at"])
    return True


def verify_second_factor(device: TwoFactorDevice, code: str) -> bool:
    """An authenticator code, or failing that a recovery code."""
    return verify_totp(device, code) or use_recovery_code(device, code)
