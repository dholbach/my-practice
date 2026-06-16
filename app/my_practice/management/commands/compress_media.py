"""
Management command to compress existing media files.

Processes all image and PDF files under MEDIA_ROOT (or a given sub-path),
compresses them in-place, and reports the space saved.

Usage:
    ./dev.py manage compress_media
    ./dev.py manage compress_media --path taxes/2025
    ./dev.py manage compress_media --dry-run
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ...utils.file_processing import (
    IMAGE_SKIP_BYTES,
    PDF_SKIP_BYTES,
    _IMAGE_EXTENSIONS,
    _PDF_EXTENSIONS,
    compress_image_inplace,
    compress_pdf_inplace,
)

_PROCESSABLE = _IMAGE_EXTENSIONS | _PDF_EXTENSIONS


class Command(BaseCommand):
    help = "Compress existing media files (images via Pillow, PDFs via Ghostscript)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default="",
            help="Sub-path within MEDIA_ROOT to process (default: entire media directory)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List files that would be processed without modifying them",
        )

    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        subpath = options["path"].lstrip("/")
        root = media_root / subpath if subpath else media_root

        if not root.exists():
            raise CommandError(f"Path not found: {root}")

        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no files will be modified\n"))

        total_files = 0
        total_compressed = 0
        total_saved = 0
        total_skipped = 0
        total_errors = 0

        for filepath in sorted(root.rglob("*")):
            if not filepath.is_file():
                continue
            ext = filepath.suffix.lower()
            if ext not in _PROCESSABLE:
                continue

            total_files += 1
            original_size = filepath.stat().st_size
            rel = filepath.relative_to(media_root)

            # Report candidates in dry-run mode
            if dry_run:
                is_image = ext in _IMAGE_EXTENSIONS
                skip_threshold = IMAGE_SKIP_BYTES if is_image else PDF_SKIP_BYTES
                label = "image" if is_image else "pdf"
                flag = "" if original_size > skip_threshold else "  (likely already small)"
                self.stdout.write(f"  [{label}] {rel}  {original_size / 1024:.0f} KB{flag}")
                continue

            try:
                if ext in _IMAGE_EXTENSIONS:
                    saved = compress_image_inplace(str(filepath))
                else:
                    saved = compress_pdf_inplace(str(filepath))

                if saved > 0:
                    total_compressed += 1
                    total_saved += saved
                    new_size = filepath.stat().st_size
                    self.stdout.write(
                        f"  ✓ {rel}"
                        f"  {original_size / 1024:.0f} → {new_size / 1024:.0f} KB"
                        f"  (-{saved / 1024:.0f} KB)"
                    )
                else:
                    total_skipped += 1
                    skip_threshold = (
                        IMAGE_SKIP_BYTES if ext in _IMAGE_EXTENSIONS else PDF_SKIP_BYTES
                    )
                    if original_size <= skip_threshold:
                        reason = f"under {skip_threshold // 1024} KB threshold"
                    else:
                        reason = f"gs found no improvement ({original_size / 1024:.0f} KB)"
                    self.stdout.write(f"  – {rel}  ({reason})")

            except Exception as exc:
                total_errors += 1
                self.stdout.write(self.style.ERROR(f"  ✗ {rel}: {exc}"))

        if dry_run:
            self.stdout.write(f"\n{total_files} processable files found.")
            self.stdout.write("Re-run without --dry-run to compress them.")
            return

        saved_kb = total_saved / 1024
        saved_mb = saved_kb / 1024
        size_str = f"{saved_mb:.1f} MB" if saved_mb >= 1 else f"{saved_kb:.0f} KB"

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone: {total_files} files scanned, "
                f"{total_compressed} compressed ({size_str} saved), "
                f"{total_skipped} skipped, "
                f"{total_errors} errors"
            )
        )

        if total_errors:
            self.stdout.write(self.style.WARNING("Check logs above for error details."))
