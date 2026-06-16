"""Management command to prune old backup files (P-007)."""

import glob
import os
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Alte Backup-Dateien löschen (Standard: älter als 30 Tage)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Maximales Alter der Backups in Tagen (Standard: 30)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nur anzeigen, was gelöscht werden würde (kein tatsächliches Löschen)",
        )
        parser.add_argument(
            "--backup-dir",
            default="/app/backups",
            help="Verzeichnis mit Backup-Dateien (Standard: /app/backups)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]
        backup_dir = options["backup_dir"]

        if not os.path.isdir(backup_dir):
            self.stdout.write(
                self.style.WARNING(f"Backup-Verzeichnis nicht gefunden: {backup_dir}")
            )
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
                            f"({size_kb:.0f} KB, {age_days} Tage alt)"
                        )
                    else:
                        os.remove(filepath)
                        self.stdout.write(
                            f"  Gelöscht: {os.path.basename(filepath)} "
                            f"({size_kb:.0f} KB, {age_days} Tage alt)"
                        )
                    deleted += 1

        action = "Würde löschen" if dry_run else "Gelöscht"
        self.stdout.write(
            self.style.SUCCESS(f"{action}: {deleted} Datei(en) älter als {days} Tage")
        )
