"""pytest-only fixtures (`./dev.py test --smart`); the Django runner ignores this file."""

import pytest
from django.conf import settings
from django.utils import translation


@pytest.fixture(autouse=True)
def _reset_active_language():
    """Start every test in the default language.

    LocaleMiddleware activates the request's language on the test thread and
    nothing switches it back, so a test that sends an English cookie leaves
    later tests running in English. The Django runner's order happened to hide
    that; testmon's order did not (#752).
    """
    translation.activate(settings.LANGUAGE_CODE)
    yield
    translation.activate(settings.LANGUAGE_CODE)
