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
import warnings
from pathlib import Path

import pypdf
from django.core.files.base import ContentFile
from django.utils.translation import gettext as _
from PIL import Image, ImageOps

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
    img = ImageOps.exif_transpose(img)  # honour scanner EXIF orientation before stripping EXIF
    if img.mode != "RGB":
        img = img.convert("RGB")
    if max(img.size) > MAX_IMAGE_PX:
        img.thumbnail((MAX_IMAGE_PX, MAX_IMAGE_PX), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    stem = Path(getattr(upload, "name", "file")).stem
    return ContentFile(buf.getvalue(), name=f"{stem}.jpg")


def _read_page_rotations(data: bytes) -> list[int]:
    """
    Return the /Rotate value for each page in the given PDF bytes.
    Ghostscript's pdfwrite device strips /Rotate entries, so we read them
    before compression and restore them afterwards.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            reader = pypdf.PdfReader(io.BytesIO(data))
            return [int(page.get("/Rotate", 0) or 0) for page in reader.pages]
    except Exception:
        return []


def _restore_page_rotations(data: bytes, rotations: list[int]) -> bytes:
    """
    Write /Rotate back onto each page of the PDF. Used to undo Ghostscript's
    rotation-stripping after compression.
    Returns unmodified data if rotations are all 0, empty, or pypdf fails.
    """
    if not rotations or all(r == 0 for r in rotations):
        return data
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            reader = pypdf.PdfReader(io.BytesIO(data))
        writer = pypdf.PdfWriter()
        writer.append(reader)
        for i, page in enumerate(writer.pages):
            rot = rotations[i] if i < len(rotations) else 0
            if rot:
                page[pypdf.generic.NameObject("/Rotate")] = pypdf.generic.NumberObject(rot)
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
    except Exception:
        logger.warning("Could not restore PDF page rotations; returning as-is")
        return data


def _compress_pdf_bytes(data: bytes) -> bytes:
    """
    Compress PDF bytes via Ghostscript. Returns compressed bytes, or the
    original bytes if gs is unavailable, fails, or makes the file larger.
    Page /Rotate attributes are preserved — Ghostscript strips them, so we
    read them beforehand and restore them after compression.
    """
    rotations = _read_page_rotations(data)

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

        compressed = _restore_page_rotations(Path(tmp_out).read_bytes(), rotations)
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


def _process_image_upload(upload, name: str) -> ContentFile:
    try:
        return compress_image_upload(upload)
    except Exception:
        # Re-raise: a file that claims to be an image but can't be parsed
        # should be rejected, not stored as-is (could be active content).
        logger.exception("Image compression failed for %s; rejecting upload", name)
        raise ValueError(
            _("Image file '%(name)s' could not be processed.") % {"name": name}
        ) from None


def _process_pdf_upload(upload, name: str):
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
        raise ValueError(_("File type '%(ext)s' is not allowed.") % {"ext": ext or _("unknown")})

    if content_type.startswith("image/") or ext in _IMAGE_EXTENSIONS:
        return _process_image_upload(upload, name)

    if content_type == "application/pdf" or ext in _PDF_EXTENSIONS:
        return _process_pdf_upload(upload, name)

    # Allowed but not compressed (e.g. .docx)
    return upload


# ---------------------------------------------------------------------------
# In-place helpers (operate on filesystem paths; used by compress_media and
# the practice-image post-save hook)
# ---------------------------------------------------------------------------


def compress_image_inplace(path: str, force: bool = False) -> int:
    """
    Compress an image file in-place.
    Resizes to MAX_IMAGE_PX on the longest side, fixes EXIF orientation, and re-encodes.
    Preserves the original format (no extension rename, so DB paths stay valid).
    Returns bytes saved (0 if skipped or no improvement).
    Pass force=True to bypass the size threshold (e.g. to fix orientation on small files).
    """
    original_size = os.path.getsize(path)
    ext = Path(path).suffix.lower()

    img = Image.open(path)
    # Check the raw orientation tag rather than comparing objects around
    # exif_transpose(): Pillow always returns a new copy from that call (even
    # for images with no orientation tag at all), so an identity check would
    # report "needs fixing" for every image and defeat the skip below.
    needs_orientation_fix = img.getexif().get(0x0112, 1) != 1
    # Physically rotate pixels to match EXIF orientation before stripping EXIF.
    # Without this, re-saving strips the Orientation tag and viewers see raw scanner pixels.
    img = ImageOps.exif_transpose(img)
    needs_resize = max(img.size) > MAX_IMAGE_PX

    if (
        not force
        and original_size <= IMAGE_SKIP_BYTES
        and not needs_resize
        and not needs_orientation_fix
    ):
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

    rotations = _read_page_rotations(Path(path).read_bytes())

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

        compressed = Path(tmp_path).read_bytes()
        fixed = _restore_page_rotations(compressed, rotations)
        if fixed is not compressed:  # _restore_page_rotations returns same object if no-op
            Path(tmp_path).write_bytes(fixed)
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
