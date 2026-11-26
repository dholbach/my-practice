"""Mark pending calendar events whose session is already invoiced as imported.

Until the billing signal in signals.py existed, a session invoiced outside the
approval queue left its calendar event pending, so queues built up rows for
work that was already billed. This clears that backlog once; the signal keeps
it clear from here on.
"""

from django.db import migrations


def import_billed_events(apps, schema_editor):  # noqa: ARG001
    PendingCalendarEvent = apps.get_model("my_practice", "PendingCalendarEvent")
    InvoiceItem = apps.get_model("my_practice", "InvoiceItem")
    billed_sessions = (
        InvoiceItem.objects.filter(session__isnull=False)
        .exclude(invoice__status="cancelled")
        .values("session_id")
    )
    PendingCalendarEvent.objects.filter(status="pending", session_id__in=billed_sessions).update(
        status="imported"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("my_practice", "0020_case_review"),
    ]

    operations = [
        migrations.RunPython(import_billed_events, migrations.RunPython.noop),
    ]
