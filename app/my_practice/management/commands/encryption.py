"""
Verify or rotate the keys behind the encrypted fields and encrypted files.

    manage.py encryption check    # can the configured keys open every stored value?
    manage.py encryption rotate   # re-encrypt every value and file under the first key

Rotation: put a new key in front of the old one in FERNET_KEY
(`FERNET_KEY=<new>,<old>`), restart, run `rotate`, confirm with `check`, then
drop the old key. Rows are updated with raw SQL so `updated_at` and save
signals are not touched — the content does not change, only its ciphertext.

The app can keep running. Each UPDATE only applies while the column still holds
the ciphertext that was read, so a value saved in the meantime is left alone
rather than overwritten with the older content — after the restart it is
already under the first key. A file deleted in the meantime is skipped.

Files in encrypted storage (client documents) are rotated too; `rotate` also
encrypts any still in plain text (migration 0006 already does that on
upgrade). Every file is verified before anything is written, and each is
replaced atomically.
"""

import logging

from cryptography.fernet import InvalidToken
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, models, transaction

from ...fields import EncryptionKeyError, decrypt_value, encrypted_fields, get_fernet
from ...storage import EncryptedFileSystemStorage, is_encrypted

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Check that FERNET_KEY opens every encrypted value, or rotate to the first key."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["check", "rotate"])

    def handle(self, *args, **options):
        try:
            fernet = get_fernet()
        except RuntimeError as exc:
            logger.error("Encryption %s aborted: %s", options["action"], exc)
            raise CommandError(str(exc)) from exc

        if options["action"] == "check":
            self._check()
            self._check_files(fernet)
        else:
            # Verify every file first: a file no key opens aborts before the
            # database or any file is touched.
            files = list(self._files())
            self._check_files(fernet, files, quiet=True)
            with transaction.atomic():
                self._rotate(fernet)
            self._rotate_files(fernet, files)

    def _columns(self):
        qn = connection.ops.quote_name
        for model, field_name in encrypted_fields():
            column = model._meta.get_field(field_name).column
            table = model._meta.db_table
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT {qn(model._meta.pk.column)}, {qn(column)} FROM {qn(table)} "
                    f"WHERE {qn(column)} IS NOT NULL AND {qn(column)} <> ''"
                )
                rows = cursor.fetchall()
            yield f"{model.__name__}.{field_name}", table, model._meta.pk.column, column, rows

    def _check(self):
        failures = 0
        total = 0
        for label, _table, _pk_column, _column, rows in self._columns():
            bad = 0
            for _pk, value in rows:
                try:
                    decrypt_value(value, label)
                except EncryptionKeyError:
                    bad += 1
            total += len(rows)
            failures += bad
            if bad:
                self.stdout.write(self.style.ERROR(f"{label}: {bad} of {len(rows)} unreadable"))
            elif rows:
                self.stdout.write(f"{label}: {len(rows)} OK")
        if failures:
            logger.error("Encryption check: %d of %d values unreadable", failures, total)
            raise CommandError(
                f"{failures} of {total} encrypted values cannot be opened with the configured "
                "FERNET_KEY. Add the key they were written with (comma-separated, after the "
                "current one)."
            )
        self.stdout.write(self.style.SUCCESS(f"All {total} encrypted values readable."))

    def _rotate(self, fernet):
        qn = connection.ops.quote_name
        total = 0
        for label, table, pk_column, column, rows in self._columns():
            try:
                updates = [
                    (fernet.rotate(value.encode()).decode(), pk, value) for pk, value in rows
                ]
            except InvalidToken as exc:
                logger.error("Encryption rotate failed on %s", label)
                raise CommandError(
                    f"{label}: a value cannot be opened with any configured key — run "
                    "`encryption check`. Nothing was changed."
                ) from exc
            rotated = 0
            with connection.cursor() as cursor:
                for update in updates:
                    cursor.execute(
                        f"UPDATE {qn(table)} SET {qn(column)} = %s "
                        f"WHERE {qn(pk_column)} = %s AND {qn(column)} = %s",
                        update,
                    )
                    rotated += cursor.rowcount
            total += rotated
            if updates:
                changed = len(updates) - rotated
                note = f" ({changed} changed meanwhile, left as saved)" if changed else ""
                self.stdout.write(f"{label}: {rotated} re-encrypted{note}")
        self.stdout.write(self.style.SUCCESS(f"Re-encrypted {total} values under the first key."))

    def _files(self):
        """(storage, name) for every file a row stores in encrypted storage."""
        for model in apps.get_models():
            for field in model._meta.concrete_fields:
                if not isinstance(field, models.FileField):
                    continue
                if not isinstance(field.storage, EncryptedFileSystemStorage):
                    continue
                names = model._default_manager.exclude(**{field.name: ""}).values_list(
                    field.name, flat=True
                )
                for name in names.iterator():
                    if name and field.storage.exists(name):
                        yield field.storage, name

    def _check_files(self, fernet, files=None, quiet=False):
        unreadable = []
        plaintext = 0
        files = self._files() if files is None else files
        count = 0
        for storage, name in files:
            count += 1
            data = storage.read_raw(name)
            if not is_encrypted(data):
                plaintext += 1
                continue
            try:
                fernet.decrypt(data)
            except InvalidToken:
                unreadable.append(name)
        if unreadable:
            logger.error("Encryption: %d of %d files unreadable", len(unreadable), count)
            raise CommandError(
                f"{len(unreadable)} of {count} encrypted files cannot be opened with the "
                "configured FERNET_KEY (first: "
                f"{unreadable[0]}). Nothing was changed."
            )
        if quiet:
            return
        if plaintext:
            self.stdout.write(
                self.style.WARNING(
                    f"{plaintext} of {count} files are not encrypted yet — run `encryption rotate`."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"All {count} encrypted files readable."))

    def _rotate_files(self, fernet, files):
        rotated = encrypted = gone = 0
        for storage, name in files:
            # Uploads never reuse a name, so the only concurrent change to a
            # file is its deletion (a document removed, a GDPR erasure).
            try:
                data = storage.read_raw(name)
                if is_encrypted(data):
                    storage.write_raw(name, fernet.rotate(data))
                    rotated += 1
                else:
                    storage.write_raw(name, fernet.encrypt(data))
                    encrypted += 1
            except FileNotFoundError:
                gone += 1
        note = f", {gone} deleted meanwhile" if gone else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Files: {rotated} re-encrypted, {encrypted} encrypted for the first time{note}."
            )
        )
