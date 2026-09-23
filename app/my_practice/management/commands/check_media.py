"""Management command to audit media files vs. database records.

Checks for:
  - Orphaned files: exist on disk but no DB record references them
  - Missing files:  DB record has a path but the file is gone from disk
"""

import os
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import models


def _models_with_file_fields() -> list[tuple[type[models.Model], list[str]]]:
    """Every concrete model that stores a path under MEDIA_ROOT, with its field names.

    Discovered from the app registry rather than hand-listed, because this
    command deletes whatever no field references. A model left off a hand-list
    does not merely go unreported — every one of its files is named as an
    orphan and removed by --delete-orphans. ClientDocument was missing for
    exactly that reason, which put every signed treatment contract, intake
    form and doctor's letter in the delete list.

    ImageField subclasses FileField, so Practice.logo/signature are included.
    """
    found = []
    for model in apps.get_models():
        field_names = [f.name for f in model._meta.get_fields() if isinstance(f, models.FileField)]
        if field_names:
            found.append((model, field_names))
    return found


def _db_media_paths() -> dict[str, list[str]]:
    """Return all relative media paths currently stored in the DB, grouped by model."""
    paths: dict[str, list[str]] = {}
    for model, field_names in _models_with_file_fields():
        values = [
            value
            for row in model._default_manager.values_list(*field_names)
            for value in row
            if value
        ]
        if values:
            paths[model.__name__] = values
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
