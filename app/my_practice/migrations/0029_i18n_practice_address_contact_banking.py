from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("my_practice", "0028_clientinquiry_status_idx"),
    ]

    operations = [
        migrations.AlterField(
            model_name="practice",
            name="street",
            field=models.CharField(
                default="", max_length=200, verbose_name="Street and house number"
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="postal_code",
            field=models.CharField(default="", max_length=20, verbose_name="Postal code"),
        ),
        migrations.AlterField(
            model_name="practice",
            name="city",
            field=models.CharField(default="", max_length=100, verbose_name="City"),
        ),
        migrations.AlterField(
            model_name="practice",
            name="country",
            field=models.CharField(
                blank=True, default="Deutschland", max_length=100, verbose_name="Country"
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="email",
            field=models.EmailField(default="", max_length=254, verbose_name="Email"),
        ),
        migrations.AlterField(
            model_name="practice",
            name="website",
            field=models.URLField(default="", verbose_name="Website"),
        ),
        migrations.AlterField(
            model_name="practice",
            name="phone",
            field=models.CharField(blank=True, max_length=50, verbose_name="Phone"),
        ),
        migrations.AlterField(
            model_name="practice",
            name="bank_name",
            field=models.CharField(default="", max_length=200, verbose_name="Bank name"),
        ),
        migrations.AlterField(
            model_name="practice",
            name="iban",
            field=models.CharField(default="", max_length=34, verbose_name="IBAN"),
        ),
        migrations.AlterField(
            model_name="practice",
            name="bic",
            field=models.CharField(default="", max_length=11, verbose_name="BIC"),
        ),
    ]
