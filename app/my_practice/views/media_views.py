"""
Authenticated serving of uploaded media (client documents, receipts, logos).

Every file under MEDIA_ROOT is served through this view rather than straight
off disk. Client documents are signed treatment contracts, intake forms and
doctors' letters — Art. 9 GDPR health data — stored at predictable paths
(``clients/<code>/<year>/<type>-<date>.<ext>``). A web server alias for
``/media/`` hands them to anyone who can guess a client code and a date, with
no login at all, which is what the reverse-proxy example in the docs used to
configure.

A file is served only when a database row references it and the requesting
user belongs to the practice that row belongs to. Anything else — a file on
disk no row references, another practice's file, a path that escapes
MEDIA_ROOT — is a 404, so the response does not confirm the file exists.
"""

import mimetypes
from pathlib import Path

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import Storage
from django.db import models
from django.http import FileResponse, Http404, HttpRequest
from django.utils._os import safe_join
from django.views.decorators.http import require_safe

from ..models import ClientDocument, ExpenseReceipt, Practice

# (model, file field) -> lookup from that model to the owning practice's id.
# Hand-listed on purpose: a model missing here fails closed (its files 404),
# and test_media_views checks this against every FileField in the app registry
# so a new upload field cannot ship unserved without a test going red.
MEDIA_FILE_OWNERS: dict[tuple[type[models.Model], str], str] = {
    (ClientDocument, "file"): "client__practice_id",
    (ExpenseReceipt, "file"): "expense__practice_id",
    (Practice, "logo"): "pk",
    (Practice, "signature"): "pk",
}


def media_owners(name: str) -> tuple[set[int], Storage | None]:
    """Owning practice IDs of ``name``, and the storage of a field that references it."""
    ids: set[int] = set()
    storage = None
    for (model, field), owner_lookup in MEDIA_FILE_OWNERS.items():
        rows = model._default_manager.filter(**{field: name}).values_list(owner_lookup, flat=True)
        found = [practice_id for practice_id in rows if practice_id is not None]
        if found:
            ids.update(found)
            # The field's storage decides how the bytes on disk are read —
            # client documents are encrypted, so a plain open() would serve
            # ciphertext.
            storage = storage or model._meta.get_field(field).storage
    return ids, storage


@require_safe
def serve_media(request: HttpRequest, path: str) -> FileResponse:
    """Stream a media file to a member of the practice that owns it.

    Login is enforced by LoginRequiredMiddleware before this runs.
    """
    owners, storage = media_owners(path)
    if not owners or storage is None or not request.user.practices.filter(pk__in=owners).exists():  # type: ignore[union-attr]
        raise Http404

    try:
        full_path = Path(safe_join(settings.MEDIA_ROOT, path))
    except SuspiciousFileOperation:
        raise Http404 from None
    if not full_path.is_file():
        raise Http404

    content_type, _encoding = mimetypes.guess_type(full_path.name)
    response = FileResponse(
        storage.open(path, "rb"),
        content_type=content_type or "application/octet-stream",
        filename=full_path.name,
    )
    # Health documents must not linger in shared or browser caches.
    response["Cache-Control"] = "private, no-store"
    return response
