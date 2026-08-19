from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("my_practice", "0029_i18n_practice_address_contact_banking"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="companywithdrawal",
            options={
                "ordering": ["-date"],
                "verbose_name": "Company Withdrawal",
                "verbose_name_plural": "Company Withdrawals",
            },
        ),
        migrations.AlterModelOptions(
            name="companyexpense",
            options={
                "ordering": ["-date"],
                "verbose_name": "Company Expense",
                "verbose_name_plural": "Company Expenses",
            },
        ),
        migrations.AlterField(
            model_name="pendingcalendarevent",
            name="google_event_id",
            field=models.CharField(max_length=255, unique=True, verbose_name="Google Event ID"),
        ),
    ]
