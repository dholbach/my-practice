"""System checks for configuration the app cannot run correctly without."""

from cryptography.fernet import Fernet
from django.core.checks import Error, Tags, Warning, register

from .fields import configured_keys

MISSING_KEY_HINT = (
    'Generate one with: python -c "from cryptography.fernet import Fernet; '
    'print(Fernet.generate_key().decode())" and add it to .env as FERNET_KEY.'
)


def _key_errors() -> list[Error]:
    errors = []
    for position, key in enumerate(configured_keys(), start=1):
        try:
            Fernet(key)
        except ValueError:
            errors.append(
                Error(
                    f"FERNET_KEY entry {position} is not a valid Fernet key.",
                    hint="Each comma-separated entry must be 32 url-safe base64-encoded bytes.",
                    id="my_practice.E001",
                )
            )
    return errors


@register()
def fernet_key_check(app_configs, **kwargs):
    """A malformed key fails every encrypted read; a missing one every write."""
    if not configured_keys():
        # Client and inquiry notes, clinical records and the calendar
        # credentials are all encrypted: without a key the first save of any
        # of them fails.
        return [
            Warning(
                "FERNET_KEY is not set; saving notes, clinical records, client documents or "
                "calendar credentials will fail.",
                hint=MISSING_KEY_HINT,
                id="my_practice.W001",
            )
        ]
    return _key_errors()


@register(Tags.security, deploy=True)
def fernet_key_deploy_check(app_configs, **kwargs):
    """In production a missing key is an error, not a warning."""
    if configured_keys():
        return []
    return [Error("FERNET_KEY is not set.", hint=MISSING_KEY_HINT, id="my_practice.E002")]
