"""Create the database cache table.

settings.CACHES uses django.core.cache.backends.db.DatabaseCache, which needs a
table. Django's documented route is a manual `manage.py createcachetable`, but
doing it here means the table appears wherever `migrate` already runs — the
compose command, prod.py's update flow, a fresh install — with no extra step to
remember or document.

createcachetable is idempotent, so re-running the migration on a database that
already has the table is safe.
"""

from django.core.management import call_command
from django.db import migrations


def create_cache_table(_apps, schema_editor):
    call_command("createcachetable", database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [
        ("my_practice", "0031_practice_email_template_validators"),
    ]

    operations = [
        # Reverse is a no-op: dropping the cache table on a rollback would lose
        # nothing of value, but recreating it costs nothing either, and leaving
        # it avoids a migration that can fail on a table another process is using.
        migrations.RunPython(create_cache_table, migrations.RunPython.noop),
    ]
