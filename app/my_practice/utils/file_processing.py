"""
File compression utilities for uploaded media.

New uploads  → process_upload() returns a ContentFile ready for a FileField.
Existing files → compress_image_inplace() / compress_pdf_inplace() modify on disk.

Images: Pillow resize to MAX_IMAGE_PX on the longest side + JPEG re-encode.
PDFs:   Ghostscript /ebook base preset + explicit Bicubic downsampling to GS_PDF_DPI.
"""

import contextlib
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

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB — generous for scanned documents, bounds worst case
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


# Why there is no code here that preserves page /Rotate through compression.
#
# It looks like there should be: Ghostscript's output carries no /Rotate even
# when the input page had one, so it reads as if pdfwrite drops the attribute.
# It does not. gs *applies* the rotation — it rotates the page content and
# swaps the MediaBox — and then writes no /Rotate because the page no longer
# needs one. Appearance is already correct; the metadata is just gone because
# it has been consumed.
#
# Reading /Rotate beforehand and writing it back afterwards (which this module
# did, on the strength of that misreading) therefore rotates every scanned
# document a second time: a 90° page comes out on its side, and a 180° page —
# an upside-down scan that /Rotate had been correcting — comes back upside
# down. compress_media's --rotate-pages flag was added to repair those by
# hand, treating the symptom.
#
# Verify with appearance, never with the /Rotate value: rasterise the page
# before and after and compare the pixels. That is what
# PdfCompressionRotationTest does, and it is the only check that can tell
# "rotation preserved" from "rotation applied twice".


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


def _pdf_is_parseable(data: bytes) -> bool:
    """Whether these bytes are a PDF with at least one readable page.

    The image path rejects an upload it cannot parse, on the grounds that a
    file claiming to be an image but isn't could be something else entirely.
    The same reasoning applies to PDFs, and applies with a little more force
    here: uploaded documents are linked straight from MEDIA_URL and opened in
    a new tab, so the browser is handed the file with whatever content type
    the extension implies — nothing downstream re-checks it.

    Ghostscript is not the check. _compress_pdf_bytes deliberately returns the
    original bytes whenever gs fails, so a file that is not a PDF at all still
    sails through it; that fallback exists so a working PDF is never lost to a
    compression failure, not to vouch for the content.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            reader = pypdf.PdfReader(io.BytesIO(data))
            return len(reader.pages) > 0
    except Exception:
        return False


def _compress_pdf_bytes(data: bytes) -> bytes:
    """
    Compress PDF bytes via Ghostscript. Returns compressed bytes, or the
    original bytes if gs is unavailable, fails, or makes the file larger.

    Page rotation needs no help from us — see the page-rotation note at the
    top of this module before adding any.
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
            with contextlib.suppress(OSError):
                os.unlink(p)


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
        if not _pdf_is_parseable(data):
            # Mirrors _process_image_upload: what we cannot parse, we do not
            # store. Raised as ValueError because every caller of
            # process_upload() already turns that into a form error.
            logger.warning("Rejecting %s — not a parseable PDF", name)
            raise ValueError(_("PDF file '%(name)s' could not be processed.") % {"name": name})
        compressed = _compress_pdf_bytes(data)
        return ContentFile(compressed, name=name)
    except ValueError:
        # The rejection above is the answer, not a failure to recover from —
        # the broad handler below must not turn it back into "store the
        # original", which is exactly what it is there to prevent.
        raise
    except Exception:
        logger.exception("PDF compression failed for %s; storing original", name)
        # Only the seek failures worth recovering from. Anything else is a bug
        # in the file object, and propagating beats returning an upload whose
        # read position is unknown — that would store a truncated document,
        # which is worse than failing the upload outright.
        with contextlib.suppress(OSError, ValueError):
            upload.seek(0)
        return upload


def process_upload(upload) -> ContentFile:
    """
    Compress an uploaded file for storage.
    Images are resized and converted to JPEG; PDFs are compressed via Ghostscript.
    Non-image/PDF types in the allowlist (e.g. .docx) are passed through unchanged.

    Raises ValueError for any extension not in _ALLOWED_EXTENSIONS so that
    active-content types (.svg, .html, .js, …) are never silently stored, and
    for any upload over MAX_UPLOAD_BYTES so a huge file can't be handed to
    Pillow/Ghostscript before we've even checked it's a reasonable size.
    """
    name = getattr(upload, "name", "") or ""
    ext = Path(name).suffix.lower()
    content_type = getattr(upload, "content_type", "") or ""
    size = getattr(upload, "size", None)

    if ext not in _ALLOWED_EXTENSIONS:
        raise ValueError(_("File type '%(ext)s' is not allowed.") % {"ext": ext or _("unknown")})

    if size is not None and size > MAX_UPLOAD_BYTES:
        raise ValueError(
            _("File '%(name)s' is too large (max %(max_mb)s MB).")
            % {"name": name, "max_mb": MAX_UPLOAD_BYTES // (1024 * 1024)}
        )

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
    Page rotation is preserved by Ghostscript itself — see the page-rotation
    note at the top of this module before adding any code to "fix" it.
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
