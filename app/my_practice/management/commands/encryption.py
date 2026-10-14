"""
Verify or rotate the keys behind the encrypted fields.

    manage.py encryption check    # can the configured keys open every stored value?
    manage.py encryption rotate   # re-encrypt every value under the first key

Rotation: put a new key in front of the old one in FERNET_KEY
(`FERNET_KEY=<new>,<old>`), restart, run `rotate`, confirm with `check`, then
drop the old key. Rows are updated with raw SQL so `updated_at` and save
signals are not touched — the content does not change, only its ciphertext.
"""

import logging

from cryptography.fernet import InvalidToken
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from ...fields import EncryptionKeyError, decrypt_value, encrypted_fields, get_fernet

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
        else:
            with transaction.atomic():
                self._rotate(fernet)

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
                updates = [(fernet.rotate(value.encode()).decode(), pk) for pk, value in rows]
            except InvalidToken as exc:
                logger.error("Encryption rotate failed on %s", label)
                raise CommandError(
                    f"{label}: a value cannot be opened with any configured key — run "
                    "`encryption check`. Nothing was changed."
                ) from exc
            with connection.cursor() as cursor:
                cursor.executemany(
                    f"UPDATE {qn(table)} SET {qn(column)} = %s WHERE {qn(pk_column)} = %s", updates
                )
            total += len(updates)
            if updates:
                self.stdout.write(f"{label}: {len(updates)} re-encrypted")
        self.stdout.write(self.style.SUCCESS(f"Re-encrypted {total} values under the first key."))
