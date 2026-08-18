from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("my_practice", "0027_expensecategoryrule"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="clientinquiry",
            index=models.Index(fields=["status"], name="inquiry_status_idx"),
        ),
    ]
