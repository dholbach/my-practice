"""The confirmation prompt shared by the commands that delete rows."""

import sys

from django.core.management.base import BaseCommand


def confirm_deletion(command: BaseCommand, prompt: str, skip_confirm: bool) -> bool:
    """Ask the operator to type "yes"; False (after saying so) when not confirmed.

    ``skip_confirm`` is the command's ``--yes``. Without a terminal there is nobody
    to ask, so that aborts instead of deleting.
    """
    if skip_confirm:
        return True
    if not sys.stdin.isatty():
        command.stdout.write(
            command.style.WARNING("⚠️  No interactive terminal detected. Use --yes to confirm.")
        )
        command.stdout.write(command.style.ERROR("❌ Aborted"))
        return False
    if input(prompt).lower() != "yes":
        command.stdout.write(command.style.ERROR("❌ Aborted"))
        return False
    return True
