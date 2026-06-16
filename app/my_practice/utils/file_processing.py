"""
File compression utilities for uploaded media.

New uploads  → process_upload() returns a ContentFile ready for a FileField.
Existing files → compress_image_inplace() / compress_pdf_inplace() modify on disk.

Images: Pillow resize to MAX_IMAGE_PX on the longest side + JPEG re-encode.
PDFs:   Ghostscript /ebook base preset + explicit Bicubic downsampling to GS_PDF_DPI.
"""

import io
import logging
import os
import subprocess
import tempfile
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image

logger = logging.getLogger(__name__)

MAX_IMAGE_PX = 2400  # longest side in pixels — approx A4 at 300 DPI
JPEG_QUALITY = 85
GS_PDF_PRESET = "/ebook"  # base preset; explicit downsampling flags override resolution
GS_PDF_DPI = 150  # Bicubic downsampling target for color/gray/mono images
IMAGE_SKIP_BYTES = 150_000  # skip images already under 150 KB
PDF_SKIP_BYTES = 500_000  # skip PDFs already under 500 KB

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"}
_PDF_EXTENSIONS = {".pdf"}
# Explicit allowlist — anything outside this is rejected by process_upload.
# Active-content types (.svg, .html, .xml, .js, …) are intentionally excluded.
_ALLOWED_EXTENSIONS = _IMAGE_EXTENSIONS | _PDF_EXTENSIONS | {".docx"}


# ---------------------------------------------------------------------------
# New-upload helpers (operate on in-memory file objects)
# ---------------------------------------------------------------------------


def compress_image_upload(upload) -> ContentFile:
    """
    Compress an in-memory image upload: resize + convert to JPEG.
    Returns a ContentFile with a .jpg filename.
    """
    img = Image.open(upload)
    if img.mode != "RGB":
        img = img.convert("RGB")
    if max(img.size) > MAX_IMAGE_PX:
        img.thumbnail((MAX_IMAGE_PX, MAX_IMAGE_PX), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    stem = Path(getattr(upload, "name", "file")).stem
    return ContentFile(buf.getvalue(), name=f"{stem}.jpg")


def _compress_pdf_bytes(data: bytes) -> bytes:
    """
    Compress PDF bytes via Ghostscript. Returns compressed bytes, or the
    original bytes if gs is unavailable, fails, or makes the file larger.
    """
    with (
        tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f_in,
        tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f_out,
    ):
        f_in.write(data)
        tmp_in, tmp_out = f_in.name, f_out.name

    try:
        result = subprocess.run(
            [
                "gs",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                f"-dPDFSETTINGS={GS_PDF_PRESET}",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                "-dEmbedAllFonts=true",
                "-dSubsetFonts=true",
                "-dAutoRotatePages=/None",
                "-dColorImageDownsampleType=/Bicubic",
                f"-dColorImageResolution={GS_PDF_DPI}",
                "-dGrayImageDownsampleType=/Bicubic",
                f"-dGrayImageResolution={GS_PDF_DPI}",
                "-dMonoImageDownsampleType=/Bicubic",
                f"-dMonoImageResolution={GS_PDF_DPI}",
                f"-sOutputFile={tmp_out}",
                tmp_in,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.warning("gs failed (upload): %s", result.stderr.strip())
            return data

        compressed = Path(tmp_out).read_bytes()
        return compressed if len(compressed) < len(data) else data
    except FileNotFoundError:
        logger.warning("ghostscript not found; storing PDF uncompressed")
        return data
    except Exception:
        logger.exception("PDF compression failed for upload")
        return data
    finally:
        for p in (tmp_in, tmp_out):
            try:
                os.unlink(p)
            except OSError:
                pass


def process_upload(upload) -> ContentFile:
    """
    Compress an uploaded file for storage.
    Images are resized and converted to JPEG; PDFs are compressed via Ghostscript.
    Non-image/PDF types in the allowlist (e.g. .docx) are passed through unchanged.

    Raises ValueError for any extension not in _ALLOWED_EXTENSIONS so that
    active-content types (.svg, .html, .js, …) are never silently stored.
    """
    name = getattr(upload, "name", "") or ""
    ext = Path(name).suffix.lower()
    content_type = getattr(upload, "content_type", "") or ""

    if ext not in _ALLOWED_EXTENSIONS:
        raise ValueError(f"Dateityp '{ext or 'unbekannt'}' ist nicht erlaubt.")

    if content_type.startswith("image/") or ext in _IMAGE_EXTENSIONS:
        try:
            return compress_image_upload(upload)
        except Exception:
            # Re-raise: a file that claims to be an image but can't be parsed
            # should be rejected, not stored as-is (could be active content).
            logger.exception("Image compression failed for %s; rejecting upload", name)
            raise ValueError(f"Bilddatei '{name}' konnte nicht verarbeitet werden.") from None

    if content_type == "application/pdf" or ext in _PDF_EXTENSIONS:
        try:
            upload.seek(0)
            data = upload.read()
            compressed = _compress_pdf_bytes(data)
            return ContentFile(compressed, name=name)
        except Exception:
            logger.exception("PDF compression failed for %s; storing original", name)
            try:
                upload.seek(0)
            except Exception:
                pass
            return upload

    # Allowed but not compressed (e.g. .docx)
    return upload


# ---------------------------------------------------------------------------
# In-place helpers (operate on filesystem paths; used by compress_media and
# the practice-image post-save hook)
# ---------------------------------------------------------------------------


def compress_image_inplace(path: str) -> int:
    """
    Compress an image file in-place.
    Resizes to MAX_IMAGE_PX on the longest side and re-encodes.
    Preserves the original format (no extension rename, so DB paths stay valid).
    Returns bytes saved (0 if skipped or no improvement).
    """
    original_size = os.path.getsize(path)
    ext = Path(path).suffix.lower()

    img = Image.open(path)
    needs_resize = max(img.size) > MAX_IMAGE_PX

    if original_size <= IMAGE_SKIP_BYTES and not needs_resize:
        return 0

    if img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGB")
    if needs_resize:
        img.thumbnail((MAX_IMAGE_PX, MAX_IMAGE_PX), Image.Resampling.LANCZOS)

    if ext in (".jpg", ".jpeg"):
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(path, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    elif ext == ".png":
        img.save(path, format="PNG", optimize=True)
    else:
        # Unknown format — skip rather than risk corruption
        return 0

    new_size = os.path.getsize(path)
    return max(original_size - new_size, 0)


def compress_pdf_inplace(path: str) -> int:
    """
    Compress a PDF file in-place using Ghostscript.
    Writes to a temp file in the same directory (ensures atomic rename works).
    Returns bytes saved (0 if skipped, gs unavailable, or no improvement).
    """
    original_size = os.path.getsize(path)
    if original_size <= PDF_SKIP_BYTES:
        return 0

    parent = Path(path).parent
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", dir=parent, delete=False) as tmp:
            tmp_path = tmp.name

        result = subprocess.run(
            [
                "gs",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                f"-dPDFSETTINGS={GS_PDF_PRESET}",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                "-dEmbedAllFonts=true",
                "-dSubsetFonts=true",
                "-dAutoRotatePages=/None",
                "-dColorImageDownsampleType=/Bicubic",
                f"-dColorImageResolution={GS_PDF_DPI}",
                "-dGrayImageDownsampleType=/Bicubic",
                f"-dGrayImageResolution={GS_PDF_DPI}",
                "-dMonoImageDownsampleType=/Bicubic",
                f"-dMonoImageResolution={GS_PDF_DPI}",
                f"-sOutputFile={tmp_path}",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.warning("gs failed on %s: %s", path, result.stderr.strip())
            return 0

        compressed_size = os.path.getsize(tmp_path)
        saved = original_size - compressed_size
        if saved > 0:
            os.replace(tmp_path, path)
            tmp_path = None  # replaced — don't delete
        return max(saved, 0)

    except FileNotFoundError:
        logger.warning("ghostscript not found; skipping %s", path)
        return 0
    except Exception:
        logger.exception("PDF compression failed for %s", path)
        return 0
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
