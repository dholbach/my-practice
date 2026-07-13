from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("my_practice", "0008_tax_year_note_settlement"),
    ]

    operations = [
        migrations.AddField(
            model_name="pendingcalendarevent",
            name="missing_since",
            field=models.DateTimeField(
                blank=True,
                help_text="Erster Fetch, bei dem der Termin nicht mehr im Kalender gefunden wurde",
                null=True,
                verbose_name="Fehlt seit",
            ),
        ),
    ]
