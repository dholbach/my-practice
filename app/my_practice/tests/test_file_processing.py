"""
Tests for file_processing.py — image/PDF compression for uploads and in-place files.
"""

import hashlib
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import skipIf

import pypdf
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from ..utils.file_processing import (
    IMAGE_SKIP_BYTES,
    MAX_UPLOAD_BYTES,
    PDF_SKIP_BYTES,
    _compress_pdf_bytes,
    _pdf_is_parseable,
    compress_image_inplace,
    compress_image_upload,
    compress_pdf_inplace,
    process_upload,
)
from .test_helpers import make_pdf_bytes, make_visual_pdf_bytes


def _make_jpeg_bytes(size=(800, 600), color=(200, 50, 50)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=95)
    return buf.getvalue()


class CompressImageUploadTest(TestCase):
    def test_resizes_and_converts_to_jpeg(self):
        buf = io.BytesIO()
        Image.new("RGBA", (4000, 100), (0, 0, 0, 0)).save(buf, format="PNG")
        upload = SimpleUploadedFile("scan.png", buf.getvalue(), content_type="image/png")

        result = compress_image_upload(upload)

        self.assertTrue(result.name.endswith(".jpg"))
        img = Image.open(io.BytesIO(result.read()))
        self.assertEqual(img.format, "JPEG")
        self.assertLessEqual(max(img.size), 2400)


class ProcessUploadTest(TestCase):
    def test_rejects_disallowed_extension(self):
        upload = SimpleUploadedFile("evil.svg", b"<svg></svg>", content_type="image/svg+xml")
        with self.assertRaises(ValueError):
            process_upload(upload)

    def test_image_upload_is_compressed(self):
        upload = SimpleUploadedFile("photo.jpg", _make_jpeg_bytes(), content_type="image/jpeg")
        result = process_upload(upload)
        self.assertTrue(result.name.endswith(".jpg"))

    def test_unparseable_image_raises_value_error(self):
        upload = SimpleUploadedFile("photo.jpg", b"not-an-image", content_type="image/jpeg")
        with self.assertRaises(ValueError):
            process_upload(upload)

    def test_pdf_upload_is_passed_through_process_upload(self):
        upload = SimpleUploadedFile("doc.pdf", make_pdf_bytes(), content_type="application/pdf")
        result = process_upload(upload)
        self.assertEqual(result.name, "doc.pdf")

    def test_docx_passthrough_unchanged(self):
        upload = SimpleUploadedFile(
            "notes.docx",
            b"docx-bytes",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        result = process_upload(upload)
        self.assertIs(result, upload)

    def test_unparseable_pdf_raises_value_error(self):
        # Mirrors test_unparseable_image_raises_value_error. A file claiming to
        # be a PDF but that pypdf cannot read is not stored: uploaded documents
        # are linked straight from MEDIA_URL and opened in a new tab, so the
        # browser gets handed the file with whatever content type the extension
        # implies, and nothing downstream re-checks it.
        upload = SimpleUploadedFile("doc.pdf", b"not a pdf", content_type="application/pdf")
        with self.assertRaises(ValueError):
            process_upload(upload)

    def test_unparseable_pdf_is_rejected_by_extension_alone(self):
        # Routing is `content_type == "application/pdf" or ext in _PDF_EXTENSIONS`,
        # so a misdeclared content type must not route around the check.
        upload = SimpleUploadedFile("doc.pdf", b"not a pdf", content_type="text/plain")
        with self.assertRaises(ValueError):
            process_upload(upload)

    def test_html_disguised_as_pdf_is_rejected(self):
        # The extension allowlist already blocks .html; this is the same content
        # arriving under a permitted extension.
        upload = SimpleUploadedFile(
            "invoice.pdf",
            b"<html><body><script>alert(1)</script></body></html>",
            content_type="application/pdf",
        )
        with self.assertRaises(ValueError):
            process_upload(upload)

    def test_rejection_message_names_the_file(self):
        upload = SimpleUploadedFile("beleg.pdf", b"garbage", content_type="application/pdf")
        with self.assertRaises(ValueError) as ctx:
            process_upload(upload)
        self.assertIn("beleg.pdf", str(ctx.exception))

    def test_valid_pdf_is_still_accepted(self):
        # The point of the check is to reject what cannot be parsed, not to
        # start refusing ordinary documents.
        upload = SimpleUploadedFile(
            "doc.pdf", make_pdf_bytes(num_pages=3), content_type="application/pdf"
        )
        self.assertEqual(process_upload(upload).name, "doc.pdf")

    def test_rejects_oversized_upload_before_processing(self):
        upload = SimpleUploadedFile("photo.jpg", b"x", content_type="image/jpeg")
        upload.size = MAX_UPLOAD_BYTES + 1
        with self.assertRaises(ValueError):
            process_upload(upload)

    def test_allows_upload_at_exactly_the_size_limit(self):
        upload = SimpleUploadedFile("doc.pdf", make_pdf_bytes(), content_type="application/pdf")
        upload.size = MAX_UPLOAD_BYTES
        result = process_upload(upload)
        self.assertEqual(result.name, "doc.pdf")


class PdfParseabilityTest(TestCase):
    def test_pdf_is_parseable_accepts_a_real_pdf(self):
        self.assertTrue(_pdf_is_parseable(make_pdf_bytes()))

    def test_pdf_is_parseable_rejects_garbage_and_empty_input(self):
        self.assertFalse(_pdf_is_parseable(b"not a pdf"))
        self.assertFalse(_pdf_is_parseable(b""))


def _render_pages(data: bytes) -> list[str]:
    """Rasterise every page and return a hash per page.

    Appearance is the only sound assertion about rotation. Checking the
    /Rotate value cannot distinguish "rotation preserved" from "rotation
    applied twice": Ghostscript consumes an input /Rotate by rotating the
    content and swapping the MediaBox, so an output page that looks right
    carries no /Rotate at all, and one that has been turned a second time
    carries exactly the value the original had. This module used to restore
    /Rotate onto gs output on that misreading, and every rotation test passed
    while scanned documents came back on their side or upside down.
    """
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.pdf"
        src.write_bytes(data)
        subprocess.run(
            [
                "gs",
                "-sDEVICE=png16m",
                "-r18",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                f"-sOutputFile={Path(tmp) / 'page-%03d.png'}",
                str(src),
            ],
            check=True,
            capture_output=True,
        )
        return [
            hashlib.md5(png.read_bytes()).hexdigest()
            for png in sorted(Path(tmp).glob("page-*.png"))
        ]


@skipIf(shutil.which("gs") is None, "ghostscript not installed")
class PdfCompressionRotationTest(TestCase):
    """Compression must not change how a rotated page looks."""

    def test_compression_preserves_appearance_for_every_rotation(self):
        for rotate in (0, 90, 180, 270):
            with self.subTest(rotate=rotate):
                original = make_visual_pdf_bytes((rotate,), bulk=500)
                compressed = _compress_pdf_bytes(original)
                self.assertLess(
                    len(compressed),
                    len(original),
                    "fixture must be large enough that gs actually compresses it, "
                    "otherwise the original bytes are returned and nothing is tested",
                )
                self.assertEqual(_render_pages(original), _render_pages(compressed))

    def test_compression_preserves_appearance_of_mixed_rotations(self):
        original = make_visual_pdf_bytes((0, 90, 180, 270), bulk=500)
        compressed = _compress_pdf_bytes(original)
        self.assertLess(len(compressed), len(original))
        self.assertEqual(_render_pages(original), _render_pages(compressed))

    def test_inplace_compression_preserves_appearance(self):
        # bulk large enough to clear PDF_SKIP_BYTES, or the file is skipped.
        original = make_visual_pdf_bytes((90, 180), bulk=20_000)
        self.assertGreater(len(original), PDF_SKIP_BYTES)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scan.pdf"
            path.write_bytes(original)
            saved = compress_pdf_inplace(str(path))
            self.assertGreater(saved, 0)
            self.assertEqual(_render_pages(original), _render_pages(path.read_bytes()))


class CompressPdfBytesTest(TestCase):
    def test_compresses_real_pdf_or_returns_original(self):
        pdf_bytes = make_pdf_bytes(num_pages=1)
        result = _compress_pdf_bytes(pdf_bytes)
        # gs may not shrink a trivial blank page below its own overhead;
        # either way the result must still be a valid, readable PDF.
        pypdf.PdfReader(io.BytesIO(result))

    def test_gs_not_found_returns_original(self):
        from unittest.mock import patch

        pdf_bytes = make_pdf_bytes(num_pages=1)
        with patch(
            "my_practice.utils.file_processing.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = _compress_pdf_bytes(pdf_bytes)
        self.assertEqual(result, pdf_bytes)

    def test_gs_failure_returns_original(self):
        from unittest.mock import MagicMock, patch

        pdf_bytes = make_pdf_bytes(num_pages=1)
        failed = MagicMock(returncode=1, stderr="boom")
        with patch("my_practice.utils.file_processing.subprocess.run", return_value=failed):
            result = _compress_pdf_bytes(pdf_bytes)
        self.assertEqual(result, pdf_bytes)


class CompressImageInplaceTest(TestCase):
    def _write_temp_jpeg(self, size=(4000, 100)) -> str:
        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        Image.new("RGB", size, (10, 20, 30)).save(path, format="JPEG", quality=95)
        return path

    def test_resizes_large_image_in_place(self):
        path = self._write_temp_jpeg()
        try:
            saved = compress_image_inplace(path)
            self.assertGreater(saved, 0)
            img = Image.open(path)
            self.assertLessEqual(max(img.size), 2400)
        finally:
            os.unlink(path)

    def test_skips_small_image_without_force(self):
        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        Image.new("RGB", (50, 50), (1, 2, 3)).save(path, format="JPEG")
        try:
            self.assertLess(os.path.getsize(path), IMAGE_SKIP_BYTES)
            saved = compress_image_inplace(path)
            self.assertEqual(saved, 0)
        finally:
            os.unlink(path)

    def test_recompresses_small_image_with_orientation_tag(self):
        """A small image with a non-normal EXIF orientation must NOT be skipped."""
        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        img = Image.new("RGB", (50, 50), (1, 2, 3))
        exif = img.getexif()
        exif[0x0112] = 6  # rotated 90° CW
        img.save(path, format="JPEG", exif=exif)
        try:
            saved = compress_image_inplace(path)
            self.assertGreater(saved, 0)
            self.assertEqual(Image.open(path).getexif().get(0x0112, 1), 1)
        finally:
            os.unlink(path)

    def test_force_recompresses_small_image(self):
        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        Image.new("RGB", (50, 50), (1, 2, 3)).save(path, format="JPEG", quality=100)
        try:
            saved = compress_image_inplace(path, force=True)
            self.assertGreaterEqual(saved, 0)
        finally:
            os.unlink(path)

    def test_png_is_reencoded_in_place(self):
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        Image.new("RGB", (4000, 100), (5, 5, 5)).save(path, format="PNG")
        try:
            compress_image_inplace(path)
            img = Image.open(path)
            self.assertEqual(img.format, "PNG")
            self.assertLessEqual(max(img.size), 2400)
        finally:
            os.unlink(path)

    def test_unknown_extension_is_skipped(self):
        fd, path = tempfile.mkstemp(suffix=".bmp")
        os.close(fd)
        Image.new("RGB", (4000, 100), (5, 5, 5)).save(path, format="BMP")
        try:
            saved = compress_image_inplace(path)
            self.assertEqual(saved, 0)
        finally:
            os.unlink(path)


class CompressPdfInplaceTest(TestCase):
    def test_skips_small_pdf(self):
        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        Path(path).write_bytes(make_pdf_bytes())
        try:
            self.assertLess(os.path.getsize(path), PDF_SKIP_BYTES)
            saved = compress_pdf_inplace(path)
            self.assertEqual(saved, 0)
        finally:
            os.unlink(path)

    def test_compresses_large_pdf(self):
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=200, height=200)
        # Pad the PDF past the skip threshold via a custom metadata field —
        # simplest way to guarantee size without fighting image-embedding APIs.
        writer.add_metadata({"/Padding": "X" * (PDF_SKIP_BYTES + 1000)})
        out = io.BytesIO()
        writer.write(out)

        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        Path(path).write_bytes(out.getvalue())
        try:
            self.assertGreater(os.path.getsize(path), PDF_SKIP_BYTES)
            compress_pdf_inplace(path)
            # Whatever happened (compressed or left alone on no-improvement),
            # the file must still be a valid, readable PDF.
            pypdf.PdfReader(path)
        finally:
            os.unlink(path)

    def test_gs_not_found_returns_zero(self):
        from unittest.mock import patch

        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        Path(path).write_bytes(make_pdf_bytes())
        # Force past the skip threshold.
        with open(path, "ab") as f:
            f.write(b"0" * (PDF_SKIP_BYTES + 1000))
        try:
            with patch(
                "my_practice.utils.file_processing.subprocess.run",
                side_effect=FileNotFoundError,
            ):
                saved = compress_pdf_inplace(path)
            self.assertEqual(saved, 0)
        finally:
            os.unlink(path)
