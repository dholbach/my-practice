"""Management command to audit media files vs. database records.

Checks for:
  - Orphaned files: exist on disk but no DB record references them
  - Missing files:  DB record has a path but the file is gone from disk
"""

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from ...models import CompanyExpense, Practice


def _db_media_paths() -> dict[str, list[str]]:
    """Return all relative media paths currently stored in the DB, grouped by model."""
    paths: dict[str, list[str]] = {}

    # Practice: logo + signature
    practice_paths = []
    for p in Practice.objects.all():
        if p.logo:
            practice_paths.append(str(p.logo))
        if p.signature:
            practice_paths.append(str(p.signature))
    if practice_paths:
        paths["Practice"] = practice_paths

    # CompanyExpense receipts (stored via related ExpenseReceipt objects)
    expense_paths = list(
        CompanyExpense.objects.filter(receipts__isnull=False)
        .values_list("receipts__file", flat=True)
        .distinct()
    )
    if expense_paths:
        paths["CompanyExpense"] = expense_paths

    return paths


class Command(BaseCommand):
    help = "Audit media files against database records (orphans and missing files)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete-orphans",
            action="store_true",
            help="Delete orphaned files with no DB record (without this flag: report only)",
        )

    def handle(self, *args, **options):
        delete_orphans = options["delete_orphans"]
        media_root = Path(settings.MEDIA_ROOT)

        if not media_root.exists():
            self.stdout.write(self.style.WARNING(f"MEDIA_ROOT not found: {media_root}"))
            return

        # --- Collect DB paths ---
        db_paths_by_model = _db_media_paths()
        all_db_paths: set[str] = {p for paths in db_paths_by_model.values() for p in paths}

        # --- Collect disk paths (relative to MEDIA_ROOT) ---
        disk_paths: set[str] = set()
        for root, _dirs, files in os.walk(media_root):
            for fname in files:
                abs_path = Path(root) / fname
                rel = str(abs_path.relative_to(media_root))
                disk_paths.add(rel)

        # --- Missing: in DB but not on disk ---
        missing = sorted(all_db_paths - disk_paths)
        # --- Orphans: on disk but not in DB ---
        orphans = sorted(disk_paths - all_db_paths)

        # Summary header
        self.stdout.write(self.style.HTTP_INFO(f"\nMEDIA_ROOT: {media_root}"))
        self.stdout.write(f"  Files on disk:  {len(disk_paths)}")
        self.stdout.write(f"  DB entries:     {len(all_db_paths)}")

        # --- Report missing files ---
        if missing:
            self.stdout.write(
                self.style.ERROR(f"\n❌ Missing files ({len(missing)}) — in DB, not on disk:")
            )
            for path in missing:
                # Find which model references it
                model_name = next(
                    (m for m, paths in db_paths_by_model.items() if path in paths),
                    "?",
                )
                self.stdout.write(f"   [{model_name}] {path}")
        else:
            self.stdout.write(self.style.SUCCESS("\n✅ No missing files"))

        # --- Report orphans ---
        if orphans:
            self.stdout.write(
                self.style.WARNING(f"\n⚠️  Orphaned files ({len(orphans)}) — on disk, not in DB:")
            )
            for path in orphans:
                abs_path = media_root / path
                size_kb = abs_path.stat().st_size / 1024
                self.stdout.write(f"   {path}  ({size_kb:.0f} KB)")
                if delete_orphans:
                    abs_path.unlink()
            if delete_orphans:
                self.stdout.write(self.style.SUCCESS(f"   → {len(orphans)} files deleted"))
            else:
                self.stdout.write("   → To delete: ./dev.py manage check_media --delete-orphans")
        else:
            self.stdout.write(self.style.SUCCESS("\n✅ No orphaned files"))

        self.stdout.write("")
