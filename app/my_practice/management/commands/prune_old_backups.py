"""Management command to prune old backup files (P-007)."""

import glob
import os
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Delete old backup files (default: older than 30 days)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Maximum backup age in days (default: 30)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only show what would be deleted (no actual deletion)",
        )
        parser.add_argument(
            "--backup-dir",
            default=settings.BACKUP_DIR,
            help=f"Directory containing backup files (default: {settings.BACKUP_DIR})",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]
        backup_dir = options["backup_dir"]

        if not os.path.isdir(backup_dir):
            self.stdout.write(self.style.WARNING(f"Backup directory not found: {backup_dir}"))
            return

        cutoff = datetime.now() - timedelta(days=days)
        patterns = [
            "db_backup_*.sql.gz",
            "media_backup_*.tar.gz",
            "media_backup_*.empty",
        ]

        deleted = 0
        for pattern in patterns:
            for filepath in sorted(glob.glob(os.path.join(backup_dir, pattern))):
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                if mtime < cutoff:
                    size_kb = os.path.getsize(filepath) / 1024
                    age_days = (datetime.now() - mtime).days
                    if dry_run:
                        self.stdout.write(
                            f"  [dry-run] {os.path.basename(filepath)} "
                            f"({size_kb:.0f} KB, {age_days} days old)"
                        )
                    else:
                        os.remove(filepath)
                        self.stdout.write(
                            f"  Deleted: {os.path.basename(filepath)} "
                            f"({size_kb:.0f} KB, {age_days} days old)"
                        )
                    deleted += 1

        action = "Would delete" if dry_run else "Deleted"
        self.stdout.write(self.style.SUCCESS(f"{action}: {deleted} file(s) older than {days} days"))
