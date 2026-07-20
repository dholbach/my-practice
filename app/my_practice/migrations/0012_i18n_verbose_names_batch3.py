import datetime

import django.db.models.deletion
from django.db import migrations, models

import my_practice.models.calendar
import my_practice.models.inquiry
import my_practice.models.operational
import my_practice.models.tag


class Migration(migrations.Migration):
    dependencies = [
        ("my_practice", "0011_i18n_verbose_names_batch2"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="checklistitempause",
            options={"verbose_name": "Checklist pause", "verbose_name_plural": "Checklist pauses"},
        ),
        migrations.AlterModelOptions(
            name="clientalias",
            options={
                "ordering": ["client", "alias_name"],
                "verbose_name": "Client alias",
                "verbose_name_plural": "Client aliases",
            },
        ),
        migrations.AlterModelOptions(
            name="clientinquiry",
            options={
                "ordering": ["-inquiry_date", "-created_at"],
                "verbose_name": "Inquiry",
                "verbose_name_plural": "Inquiries",
            },
        ),
        migrations.AlterModelOptions(
            name="clienttag",
            options={
                "ordering": ["name"],
                "verbose_name": "Client tag",
                "verbose_name_plural": "Client tags",
            },
        ),
        migrations.AlterModelOptions(
            name="googlecalendartoken",
            options={
                "ordering": ["-created_at"],
                "verbose_name": "Google Calendar Token",
                "verbose_name_plural": "Google Calendar Tokens",
            },
        ),
        migrations.AlterModelOptions(
            name="marketingperiod",
            options={
                "ordering": ["-start_date"],
                "verbose_name": "Marketing period",
                "verbose_name_plural": "Marketing periods",
            },
        ),
        migrations.AlterModelOptions(
            name="operationalchecklistcompletion",
            options={
                "ordering": ["-year_month", "checklist_type"],
                "verbose_name": "Checklist completion",
                "verbose_name_plural": "Checklist completions",
            },
        ),
        migrations.AlterModelOptions(
            name="pendingcalendarevent",
            options={
                "ordering": ["event_date", "event_time"],
                "verbose_name": "Pending calendar event",
                "verbose_name_plural": "Pending calendar events",
            },
        ),
        migrations.AlterModelOptions(
            name="practicetodo",
            options={
                "ordering": ["-created_at"],
                "verbose_name": "Task",
                "verbose_name_plural": "Tasks",
            },
        ),
        migrations.AlterModelOptions(
            name="servicetype",
            options={
                "ordering": ["code"],
                "verbose_name": "Service type",
                "verbose_name_plural": "Service types",
            },
        ),
        migrations.AlterModelOptions(
            name="session",
            options={
                "ordering": ["-session_date", "-session_time"],
                "verbose_name": "Session",
                "verbose_name_plural": "Sessions",
            },
        ),
        migrations.AlterField(
            model_name="checklistitempause",
            name="checklist_type",
            field=models.CharField(
                choices=[
                    (
                        my_practice.models.operational.OperationalChecklistCompletion.ChecklistType[
                            "WEEKLY"
                        ],
                        "Weekly backup",
                    ),
                    (
                        my_practice.models.operational.OperationalChecklistCompletion.ChecklistType[
                            "MONTHLY"
                        ],
                        "Monthly restore test",
                    ),
                    (
                        my_practice.models.operational.OperationalChecklistCompletion.ChecklistType[
                            "QUARTERLY"
                        ],
                        "MicroSD offsite backup (card A/B alternating, every 2 weeks)",
                    ),
                    (
                        my_practice.models.operational.OperationalChecklistCompletion.ChecklistType[
                            "ANNUAL"
                        ],
                        "Annual security review",
                    ),
                ],
                max_length=20,
                verbose_name="Checklist type",
            ),
        ),
        migrations.AlterField(
            model_name="checklistitempause",
            name="item_id",
            field=models.CharField(
                help_text="Matches the item id in CHECKLIST_ITEMS (e.g. 'pick_card')",
                max_length=50,
                verbose_name="Item ID",
            ),
        ),
        migrations.AlterField(
            model_name="checklistitempause",
            name="paused_until",
            field=models.DateField(
                blank=True,
                help_text="Empty = indefinite. Date = pause expires automatically.",
                null=True,
                verbose_name="Paused until",
            ),
        ),
        migrations.AlterField(
            model_name="checklistitempause",
            name="reason",
            field=models.TextField(help_text="Why is this step paused?", verbose_name="Reason"),
        ),
        migrations.AlterField(
            model_name="clientalias",
            name="alias_name",
            field=models.CharField(
                help_text="Name as it appears on bank statements",
                max_length=200,
                verbose_name="Bank name",
            ),
        ),
        migrations.AlterField(
            model_name="clientalias",
            name="client",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="payment_aliases",
                to="my_practice.client",
                verbose_name="Client",
            ),
        ),
        migrations.AlterField(
            model_name="clientalias",
            name="notes",
            field=models.TextField(
                blank=True,
                help_text="e.g. 'Parent pays' or 'Former surname'",
                verbose_name="Notes",
            ),
        ),
        migrations.AlterField(
            model_name="clientinquiry",
            name="contacted_date",
            field=models.DateField(
                blank=True,
                help_text="Date of your first response / contact",
                null=True,
                verbose_name="Responded on",
            ),
        ),
        migrations.AlterField(
            model_name="clientinquiry",
            name="converted_client",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="source_inquiry",
                to="my_practice.client",
                verbose_name="Client (after onboarding)",
            ),
        ),
        migrations.AlterField(
            model_name="clientinquiry",
            name="converted_date",
            field=models.DateField(
                blank=True,
                help_text="Date of onboarding as a client",
                null=True,
                verbose_name="Onboarded on",
            ),
        ),
        migrations.AlterField(
            model_name="clientinquiry",
            name="decision_date",
            field=models.DateField(
                blank=True,
                help_text="Date of the client decision (intake or decline / not a match)",
                null=True,
                verbose_name="Decision on",
            ),
        ),
        migrations.AlterField(
            model_name="clientinquiry",
            name="email",
            field=models.EmailField(blank=True, max_length=254, verbose_name="Email"),
        ),
        migrations.AlterField(
            model_name="clientinquiry",
            name="initial_contact_notes",
            field=models.TextField(
                blank=True,
                help_text="Notes from the initial conversation (concerns, expectations, impressions)",
                verbose_name="Initial contact notes",
            ),
        ),
        migrations.AlterField(
            model_name="clientinquiry",
            name="inquiry_date",
            field=models.DateField(default=datetime.date.today, verbose_name="Date received"),
        ),
        migrations.AlterField(
            model_name="clientinquiry",
            name="intro_date",
            field=models.DateField(
                blank=True,
                help_text="Date of the intro meeting",
                null=True,
                verbose_name="Intro meeting on",
            ),
        ),
        migrations.AlterField(
            model_name="clientinquiry",
            name="language",
            field=models.CharField(
                choices=[("de", "German"), ("en", "English")],
                default="de",
                help_text="Preferred language of the person inquiring",
                max_length=2,
                verbose_name="Language",
            ),
        ),
        migrations.AlterField(
            model_name="clientinquiry",
            name="notes",
            field=models.TextField(blank=True, verbose_name="Notes"),
        ),
        migrations.AlterField(
            model_name="clientinquiry",
            name="phone",
            field=models.CharField(blank=True, max_length=50, verbose_name="Phone"),
        ),
        migrations.AlterField(
            model_name="clientinquiry",
            name="practice",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="inquiries",
                to="my_practice.practice",
                verbose_name="Practice",
            ),
        ),
        migrations.AlterField(
            model_name="clientinquiry",
            name="source",
            field=models.CharField(
                choices=[
                    (my_practice.models.inquiry.InquirySource["GOOGLE_ADS"], "Google Ads"),
                    (
                        my_practice.models.inquiry.InquirySource["GOOGLE_ORGANIC"],
                        "Google (organic)",
                    ),
                    (my_practice.models.inquiry.InquirySource["WEBSITE"], "Website"),
                    (my_practice.models.inquiry.InquirySource["REFERRAL"], "Referral"),
                    (
                        my_practice.models.inquiry.InquirySource["DIRECTORY"],
                        "Therapist directory",
                    ),
                    (
                        my_practice.models.inquiry.InquirySource["ITS_COMPLICATED"],
                        "It's Complicated",
                    ),
                    (
                        my_practice.models.inquiry.InquirySource["NETWORK"],
                        "Network / colleagues",
                    ),
                    (my_practice.models.inquiry.InquirySource["OTHER"], "Other"),
                ],
                max_length=20,
                verbose_name="Source",
            ),
        ),
        migrations.AlterField(
            model_name="clientinquiry",
            name="status",
            field=models.CharField(
                choices=[
                    (my_practice.models.inquiry.InquiryStatus["NEW"], "New"),
                    (my_practice.models.inquiry.InquiryStatus["CONTACTED"], "Contacted"),
                    (my_practice.models.inquiry.InquiryStatus["INTRO_MEETING"], "Intro meeting"),
                    (my_practice.models.inquiry.InquiryStatus["WAITLIST"], "Waitlist"),
                    (
                        my_practice.models.inquiry.InquiryStatus["IN_INTAKE"],
                        "Intake in progress",
                    ),
                    (my_practice.models.inquiry.InquiryStatus["CONVERTED"], "Onboarded"),
                    (my_practice.models.inquiry.InquiryStatus["DECLINED"], "Declined"),
                    (my_practice.models.inquiry.InquiryStatus["UNREACHABLE"], "Unreachable"),
                    (my_practice.models.inquiry.InquiryStatus["NOT_SUITABLE"], "Not a match"),
                ],
                default=my_practice.models.inquiry.InquiryStatus["NEW"],
                max_length=20,
                verbose_name="Status",
            ),
        ),
        migrations.AlterField(
            model_name="clienttag",
            name="category",
            field=models.CharField(
                choices=[
                    (my_practice.models.tag.ClientTag.Category["GENERAL"], "General"),
                    (
                        my_practice.models.tag.ClientTag.Category["ATTENTION"],
                        "Needs attention",
                    ),
                    (my_practice.models.tag.ClientTag.Category["EXIT"], "Exit reasons"),
                ],
                default="general",
                help_text="Tag category: General (informational), Needs Attention (priority), or Exit Reasons (documentation)",
                max_length=20,
                verbose_name="Category",
            ),
        ),
        migrations.AlterField(
            model_name="clienttag",
            name="color",
            field=models.CharField(
                choices=[
                    (my_practice.models.tag.ClientTag.Color["RED"], "Red"),
                    (my_practice.models.tag.ClientTag.Color["ORANGE"], "Orange"),
                    (my_practice.models.tag.ClientTag.Color["YELLOW"], "Yellow"),
                    (my_practice.models.tag.ClientTag.Color["GREEN"], "Green"),
                    (my_practice.models.tag.ClientTag.Color["BLUE"], "Blue"),
                    (my_practice.models.tag.ClientTag.Color["PURPLE"], "Purple"),
                    (my_practice.models.tag.ClientTag.Color["PINK"], "Pink"),
                    (my_practice.models.tag.ClientTag.Color["GRAY"], "Gray"),
                ],
                default="blue",
                help_text="Display color for the tag",
                max_length=20,
                verbose_name="Color",
            ),
        ),
        migrations.AlterField(
            model_name="clienttag",
            name="description",
            field=models.TextField(
                blank=True,
                help_text="Optional description of what this tag represents",
                verbose_name="Description",
            ),
        ),
        migrations.AlterField(
            model_name="clienttag",
            name="is_system",
            field=models.BooleanField(
                default=False,
                help_text="System-generated tags (like 'no-next-session') cannot be manually edited",
                verbose_name="System tag",
            ),
        ),
        migrations.AlterField(
            model_name="googlecalendartoken",
            name="practice",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="calendar_tokens",
                to="my_practice.practice",
                verbose_name="Practice",
            ),
        ),
        migrations.AlterField(
            model_name="marketingperiod",
            name="description",
            field=models.CharField(
                help_text='e.g. "Google Ads €5/day" or "It\'s Complicated Premium"',
                max_length=500,
                verbose_name="Description",
            ),
        ),
        migrations.AlterField(
            model_name="marketingperiod",
            name="end_date",
            field=models.DateField(
                blank=True, help_text="Leave empty if still active", null=True, verbose_name="To"
            ),
        ),
        migrations.AlterField(
            model_name="marketingperiod",
            name="practice",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="marketing_periods",
                to="my_practice.practice",
                verbose_name="Practice",
            ),
        ),
        migrations.AlterField(
            model_name="marketingperiod",
            name="start_date",
            field=models.DateField(verbose_name="From"),
        ),
        migrations.AlterField(
            model_name="operationalchecklistcompletion",
            name="checklist_type",
            field=models.CharField(
                choices=[
                    (
                        my_practice.models.operational.OperationalChecklistCompletion.ChecklistType[
                            "WEEKLY"
                        ],
                        "Weekly backup",
                    ),
                    (
                        my_practice.models.operational.OperationalChecklistCompletion.ChecklistType[
                            "MONTHLY"
                        ],
                        "Monthly restore test",
                    ),
                    (
                        my_practice.models.operational.OperationalChecklistCompletion.ChecklistType[
                            "QUARTERLY"
                        ],
                        "MicroSD offsite backup (card A/B alternating, every 2 weeks)",
                    ),
                    (
                        my_practice.models.operational.OperationalChecklistCompletion.ChecklistType[
                            "ANNUAL"
                        ],
                        "Annual security review",
                    ),
                ],
                max_length=20,
                verbose_name="Checklist type",
            ),
        ),
        migrations.AlterField(
            model_name="operationalchecklistcompletion",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Completed on"),
        ),
        migrations.AlterField(
            model_name="operationalchecklistcompletion",
            name="notes",
            field=models.TextField(
                blank=True,
                help_text='e.g. "Restore test OK, 676 invoices verified"',
                verbose_name="Notes",
            ),
        ),
        migrations.AlterField(
            model_name="operationalchecklistcompletion",
            name="year_month",
            field=models.DateField(
                help_text="First day of the period (e.g. 2026-03-01 for March 2026)",
                verbose_name="Period",
            ),
        ),
        migrations.AlterField(
            model_name="pendingcalendarevent",
            name="duration_minutes",
            field=models.IntegerField(verbose_name="Duration (minutes)"),
        ),
        migrations.AlterField(
            model_name="pendingcalendarevent",
            name="event_date",
            field=models.DateField(verbose_name="Date"),
        ),
        migrations.AlterField(
            model_name="pendingcalendarevent",
            name="event_time",
            field=models.TimeField(blank=True, null=True, verbose_name="Time"),
        ),
        migrations.AlterField(
            model_name="pendingcalendarevent",
            name="fetched_at",
            field=models.DateTimeField(auto_now_add=True, verbose_name="Fetched on"),
        ),
        migrations.AlterField(
            model_name="pendingcalendarevent",
            name="matched_client",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pending_calendar_events",
                to="my_practice.client",
                verbose_name="Client",
            ),
        ),
        migrations.AlterField(
            model_name="pendingcalendarevent",
            name="missing_since",
            field=models.DateTimeField(
                blank=True,
                help_text="First fetch where the event was no longer found in the calendar",
                null=True,
                verbose_name="Missing since",
            ),
        ),
        migrations.AlterField(
            model_name="pendingcalendarevent",
            name="practice",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pending_calendar_events",
                to="my_practice.practice",
                verbose_name="Practice",
            ),
        ),
        migrations.AlterField(
            model_name="pendingcalendarevent",
            name="session",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pending_calendar_event",
                to="my_practice.session",
                verbose_name="Session",
            ),
        ),
        migrations.AlterField(
            model_name="pendingcalendarevent",
            name="status",
            field=models.CharField(
                choices=[
                    (
                        my_practice.models.calendar.PendingCalendarEvent.Status["PENDING"],
                        "Pending",
                    ),
                    (
                        my_practice.models.calendar.PendingCalendarEvent.Status["IMPORTED"],
                        "Imported",
                    ),
                    (
                        my_practice.models.calendar.PendingCalendarEvent.Status["SKIPPED"],
                        "Skipped",
                    ),
                    (
                        my_practice.models.calendar.PendingCalendarEvent.Status["CANCELLED"],
                        "Cancelled",
                    ),
                ],
                default=my_practice.models.calendar.PendingCalendarEvent.Status["PENDING"],
                max_length=20,
                verbose_name="Status",
            ),
        ),
        migrations.AlterField(
            model_name="pendingcalendarevent",
            name="suggested_service_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pending_calendar_events",
                to="my_practice.servicetype",
                verbose_name="Service type",
            ),
        ),
        migrations.AlterField(
            model_name="pendingcalendarevent",
            name="summary",
            field=models.CharField(max_length=500, verbose_name="Summary"),
        ),
        migrations.AlterField(
            model_name="practicetodo",
            name="is_focus",
            field=models.BooleanField(
                default=False,
                help_text="Mark as a focus task for the current week",
                verbose_name="Focus task",
            ),
        ),
        migrations.AlterField(
            model_name="practicetodo",
            name="practice",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="todos",
                to="my_practice.practice",
                verbose_name="Practice",
            ),
        ),
        migrations.AlterField(
            model_name="servicetype",
            name="default_duration",
            field=models.IntegerField(default=60, verbose_name="Default duration (minutes)"),
        ),
        migrations.AlterField(
            model_name="servicetype",
            name="name_de",
            field=models.CharField(
                blank=True,
                help_text='German name (e.g., "Psychotherapie, 60 Min.")',
                max_length=255,
                verbose_name="Name (German)",
            ),
        ),
        migrations.AlterField(
            model_name="servicetype",
            name="practice",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="service_types",
                to="my_practice.practice",
                verbose_name="Practice",
            ),
        ),
        migrations.AlterField(
            model_name="session",
            name="billable",
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text="Non-billable sessions (e.g. intro meeting) are ignored in monthly billing",
                verbose_name="Billable",
            ),
        ),
        migrations.AlterField(
            model_name="session",
            name="calendar_event_id",
            field=models.CharField(
                blank=True,
                help_text="Google Calendar event ID if imported",
                max_length=200,
                verbose_name="Calendar event ID",
            ),
        ),
        migrations.AlterField(
            model_name="session",
            name="cancelled",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Session was cancelled (no-show)",
                verbose_name="Cancelled",
            ),
        ),
        migrations.AlterField(
            model_name="session",
            name="client",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="sessions",
                to="my_practice.client",
                verbose_name="Client",
            ),
        ),
        migrations.AlterField(
            model_name="session",
            name="duration",
            field=models.IntegerField(default=60, verbose_name="Duration (minutes)"),
        ),
        migrations.AlterField(
            model_name="session",
            name="group_size",
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text="Number of participants (>1 for group sessions); affects therapist-hours calculation",
                verbose_name="Group size",
            ),
        ),
        migrations.AlterField(
            model_name="session",
            name="session_date",
            field=models.DateField(db_index=True, verbose_name="Session date"),
        ),
        migrations.AlterField(
            model_name="session",
            name="session_time",
            field=models.TimeField(
                blank=True,
                help_text="Session start (from calendar import)",
                null=True,
                verbose_name="Time",
            ),
        ),
    ]
