import datetime
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import my_practice.fields
import my_practice.models.client


class Migration(migrations.Migration):
    dependencies = [
        ("my_practice", "0009_pendingcalendarevent_missing_since"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="capacityperiod",
            options={
                "ordering": ["start_date"],
                "verbose_name": "Capacity period",
                "verbose_name_plural": "Capacity periods",
            },
        ),
        migrations.AlterModelOptions(
            name="client",
            options={
                "ordering": ["-active", "full_name"],
                "verbose_name": "Client",
                "verbose_name_plural": "Clients",
            },
        ),
        migrations.AlterModelOptions(
            name="clientdocument",
            options={
                "ordering": ["-document_date", "-created_at"],
                "verbose_name": "Client document",
                "verbose_name_plural": "Client documents",
            },
        ),
        migrations.AlterModelOptions(
            name="clientnote",
            options={
                "ordering": ["-note_date", "-created_at"],
                "verbose_name": "Client note",
                "verbose_name_plural": "Client notes",
            },
        ),
        migrations.AlterModelOptions(
            name="clientprofile",
            options={"verbose_name": "Client profile", "verbose_name_plural": "Client profiles"},
        ),
        migrations.AlterModelOptions(
            name="practice",
            options={
                "verbose_name": "Practice settings",
                "verbose_name_plural": "Practice settings",
            },
        ),
        migrations.AlterModelOptions(
            name="sessionlog",
            options={
                "ordering": ["-session__session_date"],
                "verbose_name": "Session log",
                "verbose_name_plural": "Session logs",
            },
        ),
        migrations.AlterModelOptions(
            name="supervisionitem",
            options={
                "ordering": ["-created_at"],
                "verbose_name": "Supervision topic",
                "verbose_name_plural": "Supervision topics",
            },
        ),
        migrations.AlterModelOptions(
            name="userpractice",
            options={
                "ordering": ["-created_at"],
                "verbose_name": "User-practice assignment",
                "verbose_name_plural": "User-practice assignments",
            },
        ),
        migrations.AlterField(
            model_name="capacityperiod",
            name="hours_per_week",
            field=models.PositiveSmallIntegerField(
                help_text="Available therapy hours per week from this date",
                verbose_name="Hours/week",
            ),
        ),
        migrations.AlterField(
            model_name="capacityperiod",
            name="practice",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="capacity_periods",
                to="my_practice.practice",
                verbose_name="Practice",
            ),
        ),
        migrations.AlterField(
            model_name="capacityperiod",
            name="start_date",
            field=models.DateField(verbose_name="Valid from"),
        ),
        migrations.AlterField(
            model_name="client",
            name="active",
            field=models.BooleanField(default=True, verbose_name="Active"),
        ),
        migrations.AlterField(
            model_name="client",
            name="address",
            field=models.TextField(blank=True, verbose_name="Address"),
        ),
        migrations.AlterField(
            model_name="client",
            name="cancellation_fee",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=6,
                verbose_name="Cancellation fee",
            ),
        ),
        migrations.AlterField(
            model_name="client",
            name="client_code",
            field=models.CharField(
                help_text="2-3 letter client initials (e.g., DE, JM)",
                max_length=10,
                unique=True,
                verbose_name="Client code",
            ),
        ),
        migrations.AlterField(
            model_name="client",
            name="contract_signed_date",
            field=models.DateField(
                blank=True,
                help_text="Date the treatment contract was signed",
                null=True,
                verbose_name="Contract signed",
            ),
        ),
        migrations.AlterField(
            model_name="client",
            name="cost_carrier",
            field=models.CharField(
                blank=True,
                help_text="Cost carrier / health insurance (e.g. 'self-pay', 'Allianz PKV')",
                max_length=200,
                verbose_name="Cost carrier",
            ),
        ),
        migrations.AlterField(
            model_name="client",
            name="date_of_birth",
            field=models.DateField(blank=True, null=True, verbose_name="Date of birth"),
        ),
        migrations.AlterField(
            model_name="client",
            name="email",
            field=models.EmailField(
                blank=True,
                max_length=254,
                validators=[django.core.validators.EmailValidator()],
                verbose_name="Email",
            ),
        ),
        migrations.AlterField(
            model_name="client",
            name="first_seen_date",
            field=models.DateField(
                blank=True,
                help_text="Date of the first intro session/appointment",
                null=True,
                verbose_name="First appointment",
            ),
        ),
        migrations.AlterField(
            model_name="client",
            name="full_name",
            field=models.CharField(max_length=200, verbose_name="Full name"),
        ),
        migrations.AlterField(
            model_name="client",
            name="hourly_rate_60",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("90.00"),
                help_text="Rate for 60-minute session",
                max_digits=6,
                verbose_name="Hourly rate (60 min)",
            ),
        ),
        migrations.AlterField(
            model_name="client",
            name="hourly_rate_90",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("130.00"),
                help_text="Rate for 90-minute session",
                max_digits=6,
                verbose_name="Hourly rate (90 min)",
            ),
        ),
        migrations.AlterField(
            model_name="client",
            name="intake_sent_date",
            field=models.DateField(
                blank=True,
                help_text="Date the intake form was handed out/sent",
                null=True,
                verbose_name="Intake form handed out",
            ),
        ),
        migrations.AlterField(
            model_name="client",
            name="is_online_client",
            field=models.BooleanField(
                default=False,
                help_text="Check if this client primarily has online sessions",
                verbose_name="Online client",
            ),
        ),
        migrations.AlterField(
            model_name="client",
            name="language",
            field=models.CharField(
                choices=[
                    (my_practice.models.client.Client.Language["DE"], "German"),
                    (my_practice.models.client.Client.Language["EN"], "English"),
                ],
                default=my_practice.models.client.Client.Language["DE"],
                max_length=2,
                verbose_name="Preferred language",
            ),
        ),
        migrations.AlterField(
            model_name="client",
            name="notes",
            field=models.TextField(blank=True, verbose_name="Notes"),
        ),
        migrations.AlterField(
            model_name="client",
            name="onboarding_complete_date",
            field=models.DateField(
                blank=True,
                help_text="Date the entire onboarding process was completed",
                null=True,
                verbose_name="Onboarding complete",
            ),
        ),
        migrations.AlterField(
            model_name="client",
            name="phone",
            field=models.CharField(blank=True, max_length=50, verbose_name="Phone"),
        ),
        migrations.AlterField(
            model_name="client",
            name="practice",
            field=models.ForeignKey(
                help_text="Which practice this client is assigned to",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="clients",
                to="my_practice.practice",
                verbose_name="Practice",
            ),
        ),
        migrations.AlterField(
            model_name="client",
            name="questionnaire_sent_date",
            field=models.DateField(
                blank=True,
                help_text="Date the anamnesis questionnaire was handed out/sent",
                null=True,
                verbose_name="Questionnaire handed out",
            ),
        ),
        migrations.AlterField(
            model_name="client",
            name="salutation",
            field=models.CharField(
                blank=True,
                help_text="Custom salutation for emails (e.g., 'Dear John', 'Liebe Maria'). If empty, will use 'Dear {name}' (EN) or 'Liebe:r {name}' (DE).",
                max_length=100,
                verbose_name="Email salutation",
            ),
        ),
        migrations.AlterField(
            model_name="clientdocument",
            name="client",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="documents",
                to="my_practice.client",
                verbose_name="Client",
            ),
        ),
        migrations.AlterField(
            model_name="clientdocument",
            name="description",
            field=models.CharField(blank=True, max_length=200, verbose_name="Description"),
        ),
        migrations.AlterField(
            model_name="clientdocument",
            name="document_date",
            field=models.DateField(
                default=datetime.date.today,
                help_text="Date of the document (e.g. signing date)",
                verbose_name="Document date",
            ),
        ),
        migrations.AlterField(
            model_name="clientdocument",
            name="document_type",
            field=models.CharField(
                choices=[
                    (
                        my_practice.models.client.ClientDocument.DocumentType["INTRO_NOTES"],
                        "Intro meeting (notes)",
                    ),
                    (
                        my_practice.models.client.ClientDocument.DocumentType["INTAKE"],
                        "Intake form",
                    ),
                    (
                        my_practice.models.client.ClientDocument.DocumentType["ANAMNESE"],
                        "Anamnesis questionnaire",
                    ),
                    (
                        my_practice.models.client.ClientDocument.DocumentType["CONTRACT"],
                        "Treatment contract",
                    ),
                    (
                        my_practice.models.client.ClientDocument.DocumentType["REFERRAL"],
                        "Referral",
                    ),
                    (my_practice.models.client.ClientDocument.DocumentType["OTHER"], "Other"),
                ],
                default=my_practice.models.client.ClientDocument.DocumentType["OTHER"],
                max_length=20,
                verbose_name="Document type",
            ),
        ),
        migrations.AlterField(
            model_name="clientdocument",
            name="file",
            field=models.FileField(
                help_text="PDF, JPG, PNG or DOCX",
                upload_to=my_practice.models.client.client_document_upload_path,
                verbose_name="File",
            ),
        ),
        migrations.AlterField(
            model_name="clientnote",
            name="client",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="client_notes",
                to="my_practice.client",
                verbose_name="Client",
            ),
        ),
        migrations.AlterField(
            model_name="clientnote",
            name="content",
            field=my_practice.fields.EncryptedTextField(
                help_text="Note content (encrypted, markdown supported)", verbose_name="Content"
            ),
        ),
        migrations.AlterField(
            model_name="clientnote",
            name="note_date",
            field=models.DateField(
                help_text="Date of the entry (e.g. call, supervision, note)", verbose_name="Date"
            ),
        ),
        migrations.AlterField(
            model_name="clientnote",
            name="note_type",
            field=models.CharField(
                choices=[("note", "Note"), ("supervision", "Supervision")],
                default="note",
                max_length=20,
                verbose_name="Type",
            ),
        ),
        migrations.AlterField(
            model_name="clientprofile",
            name="arbeitsdiagnose",
            field=my_practice.fields.EncryptedCharField(
                blank=True,
                help_text="Clinical working diagnosis (encrypted)",
                verbose_name="Working diagnosis",
            ),
        ),
        migrations.AlterField(
            model_name="clientprofile",
            name="case_notes",
            field=my_practice.fields.EncryptedTextField(
                blank=True,
                help_text="Themes, dynamics, challenges, future work (encrypted)",
                verbose_name="Case notes",
            ),
        ),
        migrations.AlterField(
            model_name="clientprofile",
            name="client",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="profile",
                to="my_practice.client",
                verbose_name="Client",
            ),
        ),
        migrations.AlterField(
            model_name="clientprofile",
            name="intake_notes",
            field=my_practice.fields.EncryptedTextField(
                blank=True,
                help_text="Initial session + clinical assessment (encrypted)",
                verbose_name="Intake & anamnesis",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="booking_url",
            field=models.URLField(
                blank=True,
                default="",
                help_text="Link to online appointment booking (e.g. Calendly). Automatically inserted into inquiry email templates.",
                verbose_name="Booking URL",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="commute_distance_km",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="One-way distance in km (e.g. 12). Used for the distance allowance on the tax year summary.",
                null=True,
                verbose_name="Distance to practice (km)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="email_from_name",
            field=models.CharField(
                default="",
                help_text="Name displayed in 'From' field of outgoing emails",
                max_length=200,
                verbose_name="Email sender name",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="email_signature",
            field=models.TextField(
                default="Mit freundlichen Grüßen / Best regards,\nHeilpraktiker für Psychotherapie",
                help_text="Used for all outgoing emails",
                verbose_name="Email signature",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="invoice_email_body_de",
            field=models.TextField(
                default="{salutation},\n\n{sessions_intro}anbei erhalten Sie die Rechnung {invoice_number} über {amount} vom {date}.\n\nBitte überweisen Sie den Betrag innerhalb von 14 Tagen unter Angabe der Rechnungsnummer.\n\nDie Rechnung ist als PDF im Anhang beigefügt.",
                help_text="Placeholders: {salutation}, {sessions_intro}, {invoice_number}, {amount}, {date}, {client_name}",
                verbose_name="Email body (German)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="invoice_email_body_en",
            field=models.TextField(
                default="{salutation},\n\n{sessions_intro}Please find attached invoice {invoice_number} for {amount} dated {date}.\n\nPlease transfer the amount within 14 days, stating the invoice number.\n\nThe invoice is attached as a PDF.",
                help_text="Placeholders: {salutation}, {sessions_intro}, {invoice_number}, {amount}, {date}, {client_name}",
                verbose_name="Email body (English)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="invoice_email_subject_de",
            field=models.CharField(
                default="Rechnung {invoice_number}",
                help_text="Placeholders: {invoice_number}, {amount}, {date}, {client_name}",
                max_length=200,
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
                verbose_name="Email subject (English)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="is_active",
            field=models.BooleanField(
                default=True, help_text="Inactive practices are not shown", verbose_name="Active"
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="is_kleinunternehmer",
            field=models.BooleanField(
                default=False,
                help_text="When enabled: § 19 UStG (small business) instead of § 4 No. 14 UStG (Heilpraktiker)",
                verbose_name="Kleinunternehmer regulation",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="kleinunternehmer_text_de",
            field=models.TextField(
                default="Der Betrag ist umsatzsteuerfrei nach § 19 UStG (Kleinunternehmerregelung).",
                help_text="Used when 'Kleinunternehmer regulation' is enabled",
                verbose_name="Kleinunternehmer text (German)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="kleinunternehmer_text_en",
            field=models.TextField(
                blank=True,
                default="This amount is VAT-exempt according to § 19 UStG (small business regulation).",
                help_text="Used when 'Kleinunternehmer regulation' is enabled",
                verbose_name="Kleinunternehmer text (English)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="memberships_de",
            field=models.TextField(default="", verbose_name="Memberships (German)"),
        ),
        migrations.AlterField(
            model_name="practice",
            name="monthly_target_hours",
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                help_text="Target hours (sessions) per month, e.g. 60.0. Enables capacity monitoring on the dashboard.",
                max_digits=6,
                null=True,
                verbose_name="Monthly target: hours",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="monthly_target_revenue",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Target revenue per month in €, e.g. 3000.00. Enables capacity monitoring on the dashboard.",
                max_digits=10,
                null=True,
                verbose_name="Monthly target: revenue (€)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="name",
            field=models.CharField(default="", max_length=200, verbose_name="Practitioner name"),
        ),
        migrations.AlterField(
            model_name="practice",
            name="payment_terms_days",
            field=models.IntegerField(default=14, verbose_name="Payment term (days)"),
        ),
        migrations.AlterField(
            model_name="practice",
            name="payment_terms_text_de",
            field=models.CharField(
                default="Bitte überweisen Sie den Rechnungsbetrag unter Angabe der Rechnungsnummer innerhalb von 14 Tagen auf das unten genannte Konto.",
                max_length=200,
                verbose_name="Payment terms (German)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="payment_terms_text_en",
            field=models.CharField(
                default="Please transfer the invoice amount stating the invoice number within 14 days to the account mentioned below.",
                max_length=200,
                verbose_name="Payment terms (English)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="practice_weekdays",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Weekdays on which the practice is attended (0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri).",
                verbose_name="Practice days (weekdays)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="private_bank_account",
            field=models.CharField(
                blank=True,
                help_text="IBAN of the private account, for automatic detection of withdrawals and capital contributions during bank import",
                max_length=34,
                verbose_name="Private bank account (IBAN)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="short_title",
            field=models.CharField(
                default="Therapie",
                help_text="Short label for the title bar (e.g. 'Therapy', 'Coaching')",
                max_length=50,
                verbose_name="Short title",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="signature",
            field=models.ImageField(
                blank=True, null=True, upload_to="practice/", verbose_name="Signature"
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="slug",
            field=models.SlugField(
                default="default",
                help_text="Unique identifier for the practice (e.g. 'therapy', 'coaching')",
                unique=True,
                verbose_name="URL slug",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="subtitle_de",
            field=models.CharField(
                blank=True,
                default="praxis für körperpsychotherapie",
                max_length=200,
                verbose_name="Subtitle (German)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="subtitle_en",
            field=models.CharField(
                blank=True,
                default="deutsch & english",
                max_length=200,
                verbose_name="Subtitle (English)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="tax_id",
            field=models.CharField(default="", max_length=50, verbose_name="Tax ID"),
        ),
        migrations.AlterField(
            model_name="practice",
            name="title",
            field=models.CharField(
                default="Heilpraktiker für Psychotherapie",
                max_length=200,
                verbose_name="Professional title",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="users",
            field=models.ManyToManyField(
                related_name="practices",
                through="my_practice.UserPractice",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Users",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="vat_exempt_text_de",
            field=models.TextField(
                default="Der Betrag ist umsatzsteuerfrei nach § 4 Nr. 14 UStG",
                help_text="Used when 'Kleinunternehmer regulation' is NOT enabled",
                verbose_name="VAT exemption text (German)",
            ),
        ),
        migrations.AlterField(
            model_name="practice",
            name="vat_exempt_text_en",
            field=models.TextField(
                default="This amount is exempt from VAT according to § 4 No. 14 UStG",
                help_text="Used when 'Kleinunternehmer regulation' is NOT enabled",
                verbose_name="VAT exemption text (English)",
            ),
        ),
        migrations.AlterField(
            model_name="sessionlog",
            name="content",
            field=my_practice.fields.EncryptedTextField(
                blank=True,
                help_text="Pre-filled: feeling afterward / perception / session / what helped (encrypted)",
                verbose_name="Session note",
            ),
        ),
        migrations.AlterField(
            model_name="sessionlog",
            name="interventions",
            field=my_practice.fields.EncryptedTextField(
                blank=True,
                help_text="Techniques and interventions applied (encrypted)",
                verbose_name="Interventions",
            ),
        ),
        migrations.AlterField(
            model_name="sessionlog",
            name="mood_tags",
            field=models.JSONField(
                default=list,
                help_text="Selection from predefined signals (unencrypted, for triage)",
                verbose_name="Mood tags",
            ),
        ),
        migrations.AlterField(
            model_name="sessionlog",
            name="next_session_ideas",
            field=my_practice.fields.EncryptedTextField(
                blank=True,
                help_text="Themes, interventions, homework for the next session (encrypted)",
                verbose_name="Ideas for next session",
            ),
        ),
        migrations.AlterField(
            model_name="sessionlog",
            name="session",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="log",
                to="my_practice.session",
                verbose_name="Session",
            ),
        ),
        migrations.AlterField(
            model_name="sessionlog",
            name="session_type",
            field=models.CharField(
                choices=[
                    ("erstgespraech", "Initial session"),
                    ("standard", "Standard"),
                    ("krisenintervention", "Crisis intervention"),
                    ("abschlussphase", "Closing phase"),
                    ("ausfall", "No-show / cancellation"),
                ],
                default="standard",
                max_length=30,
                verbose_name="Session type",
            ),
        ),
        migrations.AlterField(
            model_name="sessionlog",
            name="summary",
            field=models.CharField(
                blank=True,
                default="",
                help_text="One-liner for the overview (unencrypted, max. 120 characters)",
                max_length=120,
                verbose_name="Short summary",
            ),
        ),
        migrations.AlterField(
            model_name="sessionlog",
            name="therapist_reflection",
            field=my_practice.fields.EncryptedTextField(
                blank=True,
                help_text="How I felt about it — countertransference (encrypted, separate)",
                verbose_name="Own reflection",
            ),
        ),
        migrations.AlterField(
            model_name="supervisionitem",
            name="client",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="supervision_items",
                to="my_practice.client",
                verbose_name="Client",
            ),
        ),
        migrations.AlterField(
            model_name="supervisionitem",
            name="content",
            field=my_practice.fields.EncryptedTextField(
                help_text="Supervision question or topic (encrypted)", verbose_name="Content"
            ),
        ),
        migrations.AlterField(
            model_name="supervisionitem",
            name="status",
            field=models.CharField(
                choices=[("offen", "Open"), ("besprochen", "Discussed")],
                default="offen",
                max_length=20,
                verbose_name="Status",
            ),
        ),
        migrations.AlterField(
            model_name="userpractice",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, verbose_name="Created on"),
        ),
        migrations.AlterField(
            model_name="userpractice",
            name="is_owner",
            field=models.BooleanField(
                default=False,
                help_text="Owners have full administrative rights",
                verbose_name="Owner",
            ),
        ),
        migrations.AlterField(
            model_name="userpractice",
            name="practice",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="memberships",
                to="my_practice.practice",
                verbose_name="Practice",
            ),
        ),
        migrations.AlterField(
            model_name="userpractice",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="practice_memberships",
                to=settings.AUTH_USER_MODEL,
                verbose_name="User",
            ),
        ),
    ]
