"""
Second sign-in factor: a TOTP authenticator app, plus single-use recovery codes.

The secret is encrypted like the clinical notes — a database dump alone must
not be enough to mint valid codes.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from ..fields import EncryptedCharField
from .base import TimestampedModel


class TwoFactorDevice(TimestampedModel):
    """A user's authenticator-app secret. Unconfirmed until the first valid code."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="two_factor_device",
        verbose_name=_("User"),
    )
    secret = EncryptedCharField(verbose_name=_("Secret"))
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Confirmed at"))
    # The newest 30-second time step a code was accepted for. A code is valid
    # for up to 90 seconds (one step of clock drift either side); refusing any
    # step at or before this one stops a code seen over a shoulder or in a
    # proxy log from being used a second time.
    last_used_step = models.BigIntegerField(default=0)

    class Meta:
        verbose_name = _("Two-factor device")
        verbose_name_plural = _("Two-factor devices")

    def __str__(self) -> str:
        return f"{self.user} ({'confirmed' if self.confirmed_at else 'pending'})"

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None


class RecoveryCode(models.Model):
    """A single-use code for when the authenticator app is lost. Stored hashed."""

    device = models.ForeignKey(
        TwoFactorDevice,
        on_delete=models.CASCADE,
        related_name="recovery_codes",
        verbose_name=_("Two-factor device"),
    )
    code_hash = models.CharField(max_length=64, verbose_name=_("Code hash"))
    used_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Used at"))

    class Meta:
        verbose_name = _("Recovery code")
        verbose_name_plural = _("Recovery codes")

    def __str__(self) -> str:
        return f"{self.device.user} ({'used' if self.used_at else 'unused'})"


class LoginThrottle(TimestampedModel):
    """Failed sign-in attempts for one throttle key, until ``expires_at``.

    A table of its own rather than the cache: the database cache culls a third
    of its entries once it holds 300, so a flood of junk usernames used to
    evict the counter of the account being guessed. Rows here only go once
    they have expired.
    """

    # sha256 hex of the username/address pair or user id; never the username.
    key = models.CharField(max_length=64, unique=True, verbose_name=_("Key"))
    failures = models.PositiveIntegerField(default=0, verbose_name=_("Failures"))
    expires_at = models.DateTimeField(db_index=True, verbose_name=_("Expires at"))

    class Meta:
        verbose_name = _("Sign-in throttle")
        verbose_name_plural = _("Sign-in throttles")

    def __str__(self) -> str:
        return f"{self.key[:12]}… ({self.failures})"
