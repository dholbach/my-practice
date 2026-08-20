from django.db import migrations, models

import my_practice.validators


class Migration(migrations.Migration):
    """Attach validate_email_template_placeholders to the invoice email template fields.

    No schema change — validators are enforced by full_clean()/ModelForm, so this
    is a state-only AlterField on all four fields.
    """

    dependencies = [
        ("my_practice", "0030_i18n_withdrawal_expense_calendar_verbose_names"),
    ]

    operations = [
        migrations.AlterField(
            model_name="practice",
            name="invoice_email_subject_de",
            field=models.CharField(
                default="Rechnung {invoice_number}",
                help_text="Placeholders: {invoice_number}, {amount}, {date}, {client_name}",
                max_length=200,
                validators=[my_practice.validators.validate_email_template_placeholders],
                verbose_name="Email subject (German)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="invoice_email_subject_en",
            field=models.CharField(
                default="Invoice {invoice_number}",
                help_text="Placeholders: {invoice_number}, {amount}, {date}, {client_name}",
                max_length=200,
                validators=[my_practice.validators.validate_email_template_placeholders],
                verbose_name="Email subject (English)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="invoice_email_body_de",
            field=models.TextField(
                default="{salutation},\n\n{sessions_intro}anbei erhalten Sie die Rechnung {invoice_number} über {amount} vom {date}.\n\nBitte überweisen Sie den Betrag innerhalb von 14 Tagen unter Angabe der Rechnungsnummer.\n\nDie Rechnung ist als PDF im Anhang beigefügt.",
                help_text="Placeholders: {salutation}, {sessions_intro}, {invoice_number}, {amount}, {date}, {client_name}",
                validators=[my_practice.validators.validate_email_template_placeholders],
                verbose_name="Email body (German)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="invoice_email_body_en",
            field=models.TextField(
                default="{salutation},\n\n{sessions_intro}Please find attached invoice {invoice_number} for {amount} dated {date}.\n\nPlease transfer the amount within 14 days, stating the invoice number.\n\nThe invoice is attached as a PDF.",
                help_text="Placeholders: {salutation}, {sessions_intro}, {invoice_number}, {amount}, {date}, {client_name}",
                validators=[my_practice.validators.validate_email_template_placeholders],
                verbose_name="Email body (English)",
            ),
        ),
    ]
