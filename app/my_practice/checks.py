"""System checks for configuration the app cannot run correctly without."""

from cryptography.fernet import Fernet
from django.conf import settings
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
def fernet_key_check(**kwargs):
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
def fernet_key_deploy_check(**kwargs):
    """In production a missing key is an error, not a warning."""
    if configured_keys():
        return []
    return [Error("FERNET_KEY is not set.", hint=MISSING_KEY_HINT, id="my_practice.E002")]


@register(Tags.security)
def secret_key_check(**kwargs):
    """
    Refuse the fallback SECRET_KEY outside DEBUG.

    Django's own security.W009 only runs under `check --deploy` and is a
    warning. This runs on every `migrate`, which the prod container does before
    starting gunicorn, so a missing DJANGO_SECRET_KEY stops the start instead
    of signing sessions and password-reset tokens with a key from the repo.
    Skipped under tests: the runner forces DEBUG off before it runs checks.
    """
    if settings.DEBUG or settings.RUNNING_TESTS:
        return []
    if not settings.SECRET_KEY.startswith("django-insecure"):
        return []
    return [
        Error(
            "SECRET_KEY is a django-insecure placeholder while DEBUG is off.",
            hint="Set DJANGO_SECRET_KEY in .env (./prod.py generates one).",
            id="my_practice.E003",
        )
    ]
