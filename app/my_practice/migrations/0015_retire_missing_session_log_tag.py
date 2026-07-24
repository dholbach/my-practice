"""
Retire the missing-session-log ClientTag (P-050): the Focus Queue now
materializes this as a per-session Task (more precise, actionable, and
already reusing the same detection query) rather than a client-level tag.
Nothing else reads this tag — the client list's 📝 indicator is a separate
live query, independent of it.
"""

from django.db import migrations


def delete_missing_session_log_tag(apps, schema_editor):
    ClientTag = apps.get_model("my_practice", "ClientTag")
    ClientTag.objects.filter(slug="missing-session-log").delete()


def noop_reverse(apps, schema_editor):
    """Not reconstructed on reverse — update_client_tags no longer knows this tag."""
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("my_practice", "0014_add_task_fields_to_practicetodo"),
    ]

    operations = [
        migrations.RunPython(delete_missing_session_log_tag, noop_reverse),
    ]
