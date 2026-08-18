"""
Tests for the compress_media management command.
"""

import io
import os
import tempfile
from io import StringIO
from pathlib import Path

import pypdf
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from PIL import Image


def _make_pdf_bytes(num_pages=1, rotate=0) -> bytes:
    writer = pypdf.PdfWriter()
    for _ in range(num_pages):
        page = writer.add_blank_page(width=200, height=200)
        if rotate:
            page.rotate(rotate)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class CompressMediaTest(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self._override = override_settings(MEDIA_ROOT=self.media_root)
        self._override.enable()
        self.addCleanup(self._override.disable)

    def _write(self, rel_path: str, content: bytes) -> str:
        path = Path(self.media_root) / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)

    def _run(self, *args):
        out = StringIO()
        call_command("compress_media", *args, stdout=out)
        return out.getvalue()

    def test_missing_path_raises_command_error(self):
        with self.assertRaises(CommandError):
            self._run("--path", "does/not/exist")

    def test_dry_run_lists_files_without_modifying(self):
        large_jpeg = Image.new("RGB", (4000, 100), (10, 20, 30))
        buf = io.BytesIO()
        large_jpeg.save(buf, format="JPEG", quality=95)
        path = self._write("clients/ab-1/scan.jpg", buf.getvalue())
        original_bytes = Path(path).read_bytes()

        output = self._run("--dry-run")

        self.assertIn("scan.jpg", output)
        self.assertEqual(Path(path).read_bytes(), original_bytes)

    def test_dry_run_ignores_non_processable_extensions(self):
        self._write("clients/ab-1/notes.txt", b"not processable")

        output = self._run("--dry-run")

        self.assertNotIn("notes.txt", output)
        self.assertIn("0 processable files found", output)

    def test_path_option_scopes_to_subdirectory(self):
        buf = io.BytesIO()
        Image.new("RGB", (50, 50), (1, 2, 3)).save(buf, format="JPEG")
        self._write("clients/ab-1/scan.jpg", buf.getvalue())
        self._write("clients/cd-2/other.jpg", buf.getvalue())

        output = self._run("--dry-run", "--path", "clients/ab-1")

        self.assertIn("scan.jpg", output)
        self.assertNotIn("other.jpg", output)

    def test_rotate_pages_dry_run_does_not_modify(self):
        path = self._write("clients/ab-1/scan.pdf", _make_pdf_bytes())
        original_bytes = Path(path).read_bytes()

        output = self._run("--dry-run", "--rotate-pages", "180")

        self.assertIn("scan.pdf", output)
        self.assertEqual(Path(path).read_bytes(), original_bytes)

    def test_rotate_pages_sets_rotation_on_pdf(self):
        path = self._write("clients/ab-1/scan.pdf", _make_pdf_bytes())

        self._run("--rotate-pages", "180")

        reader = pypdf.PdfReader(path)
        self.assertEqual(int(reader.pages[0].get("/Rotate", 0)), 180)

    def test_compresses_large_image_in_place(self):
        buf = io.BytesIO()
        Image.new("RGB", (4000, 100), (10, 20, 30)).save(buf, format="JPEG", quality=95)
        path = self._write("clients/ab-1/scan.jpg", buf.getvalue())
        original_size = os.path.getsize(path)

        output = self._run()

        self.assertIn("1 compressed", output)
        self.assertLess(os.path.getsize(path), original_size)

    def test_skips_small_image_without_force(self):
        buf = io.BytesIO()
        Image.new("RGB", (50, 50), (1, 2, 3)).save(buf, format="JPEG")
        self._write("clients/ab-1/scan.jpg", buf.getvalue())

        output = self._run()

        self.assertIn("1 skipped", output)
        self.assertIn("0 compressed", output)
