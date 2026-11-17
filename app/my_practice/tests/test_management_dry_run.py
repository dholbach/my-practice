"""Every management command that changes data can be asked to only preview.

The commands grew four spellings (``--apply``, ``--dry-run``, ``--delete-orphans``
and none at all). ``--dry-run`` is now the one that always means "show, change
nothing"; the older flags stay because the scheduled jobs call them, and each
command keeps its own safe default. A new command that deletes or rewrites
data belongs in this list.
"""

from django.core.management import get_commands, load_command_class
from django.test import SimpleTestCase

DATA_CHANGING_COMMANDS = (
    "check_media",
    "clearbanktransactions",
    "compress_media",
    "fetch_calendar_events",
    "remove_financial_duplicates",
    "tidy_inquiries",
)


class DryRunFlagTests(SimpleTestCase):
    def test_data_changing_commands_accept_dry_run(self):
        for name in DATA_CHANGING_COMMANDS:
            with self.subTest(command=name):
                command = load_command_class(get_commands()[name], name)
                parser = command.create_parser("manage.py", name)
                options = {s for action in parser._actions for s in action.option_strings}
                self.assertIn("--dry-run", options)
