"""
Management command that runs the practice's hourly background jobs in
sequence: calendar sync, client tag recalculation, and Focus Queue
materialization.

Consolidates what used to be three separately-timed systemd units into one
(scripts/my-practice-scheduled-jobs.timer/.service, see
docs/operations/SCRIPTS.md) — self-hosters install and monitor a single
job instead of three. Each underlying command is independently idempotent
and safe to run hourly (fetch_calendar_events was already hourly;
update_client_tags recomputes and diffs tag state; sync_focus_queue_tasks
materializes/auto-closes derived rows), so folding sync_focus_queue_tasks's
former daily cadence into this hourly run is safe.

A failure in one job is logged and does not prevent the others from
running — only after all three have been attempted does the command raise,
so a transient Google Calendar API error doesn't also skip tag updates.
Any of the three commands can still be run individually for manual/debug use.
"""

import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

JOBS = ["fetch_calendar_events", "update_client_tags", "sync_focus_queue_tasks"]


class Command(BaseCommand):
    help = (
        "Run the hourly background jobs (calendar sync, client tag "
        "recalculation, Focus Queue materialization) in sequence."
    )

    def handle(self, *args, **options):
        failures = []
        for job in JOBS:
            self.stdout.write(f"--- {job} ---")
            try:
                call_command(job, stdout=self.stdout, stderr=self.stderr)
            except Exception as e:
                logger.error(f"Scheduled job '{job}' failed: {e}")
                self.stderr.write(self.style.ERROR(f"{job} failed: {e}"))
                failures.append(job)

        if failures:
            raise CommandError(f"Scheduled job(s) failed: {', '.join(failures)}")
        self.stdout.write(self.style.SUCCESS("All scheduled jobs completed."))
