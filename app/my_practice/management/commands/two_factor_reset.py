"""
Turn off two-factor sign-in for a user who lost both phone and recovery codes.

    ./prod.py manage two_factor_reset <username>

Needs shell access to the server, which already means full control of the
installation, so it grants nothing an attacker at that point lacks. The user
signs in with their password alone and can set up a new authenticator.
Every existing session of theirs is ended: a reset after a lost phone may
also be a reset after a stolen laptop.
"""

import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from ...models import TwoFactorDevice
from ...utils.two_factor import end_other_sessions

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Remove a user's authenticator and recovery codes (two-factor sign-in off)."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        username = options["username"]
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            logger.error("two_factor_reset: no user %r", username)
            raise CommandError(f"No user named {username!r}.")
        deleted, _detail = TwoFactorDevice.objects.filter(user=user).delete()
        ended = end_other_sessions(user)
        if not deleted:
            self.stdout.write(f"{username} has no two-factor device; nothing to do.")
            return
        logger.warning("Two-factor sign-in reset for %s from the command line", username)
        self.stdout.write(
            self.style.SUCCESS(
                f"Two-factor sign-in turned off for {username}; {ended} session(s) signed out."
            )
        )
