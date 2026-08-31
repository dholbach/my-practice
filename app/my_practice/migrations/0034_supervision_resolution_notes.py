"""
Merge the two "Supervision" entry points on the client detail page into one.

SupervisionItem (open/discussed topic queue) and ClientNote note_type="supervision"
(dated markdown feedback notes) covered overlapping ground and confused the UI.
SupervisionItem gains resolution_notes/resolved_date so a topic can carry its
outcome when marked discussed; existing supervision-type ClientNotes are migrated
in as already-discussed SupervisionItems (content = the note's text, resolved_date
= the note's date) and then removed.
"""

from django.db import migrations, models

import my_practice.fields


def migrate_supervision_notes(apps, schema_editor):
    ClientNote = apps.get_model("my_practice", "ClientNote")
    SupervisionItem = apps.get_model("my_practice", "SupervisionItem")

    supervision_notes = ClientNote.objects.filter(note_type="supervision")
    for note in supervision_notes:
        SupervisionItem.objects.create(
            client_id=note.client_id,
            content=note.content,
            status="besprochen",
            resolved_date=note.note_date,
        )
    supervision_notes.delete()


def noop_reverse(apps, schema_editor):
    """Not reconstructed on reverse — migrated rows stay as SupervisionItems."""
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("my_practice", "0033_googlecalendartoken_calendar_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="supervisionitem",
            name="resolution_notes",
            field=my_practice.fields.EncryptedTextField(
                blank=True,
                default="",
                help_text="Feedback or outcome once discussed (optional, encrypted)",
                verbose_name="Resolution notes",
            ),
        ),
        migrations.AddField(
            model_name="supervisionitem",
            name="resolved_date",
            field=models.DateField(blank=True, null=True, verbose_name="Discussed on"),
        ),
        migrations.RunPython(migrate_supervision_notes, noop_reverse),
        migrations.RemoveField(
            model_name="clientnote",
            name="note_type",
        ),
        migrations.AlterField(
            model_name="clientnote",
            name="note_date",
            field=models.DateField(
                help_text="Date of the entry (e.g. call, note)", verbose_name="Date"
            ),
        ),
    ]
