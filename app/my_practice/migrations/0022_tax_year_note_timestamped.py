import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("my_practice", "0021_remove_leistungserfassung_leistung_session_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="taxyearnote",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
