"""
Encrypted file storage for client documents.

Client documents — intake forms, anamnesis questionnaires, signed treatment
contracts, doctors' letters — are Art. 9 GDPR health data, as sensitive as
the clinical notes. EncryptedFileSystemStorage stores each file as one Fernet
token under the same FERNET_KEY as the encrypted fields, so the media
directory and every backup of it are unreadable without the key.

Files are read and written whole: Fernet has no streaming mode, and uploads
are capped at MAX_UPLOAD_BYTES after compression anyway.

A file written before encryption was introduced (it does not start with the
Fernet token prefix) is returned as-is, so a deployment keeps working between
`migrate` and `manage.py encryption rotate`, which encrypts those files.
"""

import os
import tempfile

from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible

from .fields import decrypt_bytes, get_fernet

# Every Fernet token starts with version byte 0x80 and a 64-bit timestamp,
# which base64-encode to this prefix. No PDF, JPEG, PNG or DOCX starts so.
FERNET_PREFIX = b"gAAAAA"


def is_encrypted(data: bytes) -> bool:
    """Whether `data` is a Fernet token rather than a plain file."""
    return data.startswith(FERNET_PREFIX)


@deconstructible
class EncryptedFileSystemStorage(FileSystemStorage):
    """FileSystemStorage that encrypts file contents at rest."""

    def _save(self, name, content):
        content.seek(0)
        ciphertext = get_fernet().encrypt(content.read())
        return super()._save(name, ContentFile(ciphertext))

    def _open(self, name, mode="rb"):
        if "w" in mode or "a" in mode or "+" in mode:
            raise ValueError("EncryptedFileSystemStorage files are read-only; save a new file.")
        with super()._open(name, "rb") as handle:
            data = handle.read()
        if is_encrypted(data):
            data = decrypt_bytes(data, f"media file {name}")
        return ContentFile(data, name=name)

    def read_raw(self, name: str) -> bytes:
        """The bytes on disk, without decrypting."""
        with super()._open(name, "rb") as handle:
            return handle.read()

    def write_raw(self, name: str, data: bytes) -> None:
        """Atomically replace the bytes on disk of an existing file, keeping its mode."""
        path = self.path(name)
        mode = os.stat(path).st_mode & 0o777
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".enc-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.chmod(tmp, mode)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise


def client_document_storage() -> EncryptedFileSystemStorage:
    """Storage for ClientDocument.file (a callable, so migrations record a reference)."""
    return EncryptedFileSystemStorage()
