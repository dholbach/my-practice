"""
Shared field validators.

Deliberately dependency-free (no models, no utils): ``models/practice.py``
imports from here, and anything that reaches ``my_practice.utils`` from a model
module triggers ``utils/__init__.py``, which imports builders that import
``..models`` — a circular import during model loading.
"""

import re

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"}
PDF_EXTENSIONS = {".pdf"}
# Explicit allowlist — anything outside this is rejected by process_upload.
# Active-content types (.svg, .html, .xml, .js, …) are intentionally excluded.
UPLOAD_EXTENSIONS = IMAGE_EXTENSIONS | PDF_EXTENSIONS | {".docx"}

# The same allowlists on the model fields, so an upload that bypasses
# process_upload (the admin inlines) is held to them too. For the ImageFields
# this is narrower than Django's default, which accepts anything Pillow can
# open — including .eps/.ps, which Pillow hands to Ghostscript.
validate_upload_extension = FileExtensionValidator(sorted(e[1:] for e in UPLOAD_EXTENSIONS))
validate_image_extension = FileExtensionValidator(sorted(e[1:] for e in IMAGE_EXTENSIONS))

# A placeholder is exactly ``{word}``. Deliberately narrow: it is also what
# render_email_template() substitutes, so validation and rendering agree on
# what counts as a placeholder, and attribute/index traversal such as
# ``{client.__class__}`` is not a placeholder at all.
PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

# Every key get_invoice_email_content() puts in the render context. Both the
# subject and the body templates are rendered against the same dict.
INVOICE_EMAIL_PLACEHOLDERS = frozenset(
    {"salutation", "sessions_intro", "invoice_number", "amount", "date", "client_name"}
)


def validate_email_template_placeholders(value: str) -> None:
    """Reject invoice email templates containing unknown ``{placeholders}``.

    Rendering leaves an unknown placeholder standing rather than raising (see
    render_email_template), so without this a typo'd ``{Betrag}`` would reach
    the client verbatim in an otherwise normal-looking email. Catching it at
    save time puts the error in front of the one person who can fix it.
    """
    unknown = sorted(set(PLACEHOLDER_RE.findall(value or "")) - INVOICE_EMAIL_PLACEHOLDERS)
    if unknown:
        raise ValidationError(
            gettext("Unknown placeholder(s): %(unknown)s. Available: %(available)s"),
            params={
                "unknown": ", ".join("{%s}" % u for u in unknown),
                "available": ", ".join("{%s}" % p for p in sorted(INVOICE_EMAIL_PLACEHOLDERS)),
            },
        )
