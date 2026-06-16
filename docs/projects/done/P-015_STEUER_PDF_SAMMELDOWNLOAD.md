# P-015: Steuer-PDF-Sammeldownload

**Status**: ✅ DONE
**Completed**: 4. März 2026
**Priority**: MEDIUM
**Created**: 2026-03-04
**Cross-ref**: [PROJECTS.md](../../../PROJECTS.md)

Batch download of all invoices for a given year as a single ZIP file,
suitable for the annual tax declaration (Steuererklärung).

---

## Feature Description

A single-click download button on both the invoice list and the tax quarter
overview that generates a ZIP archive of all invoices for the selected year.

**URL**: `GET /invoices/batch-pdf/?year=YYYY&status=paid`

**Response**: `Rechnungen_{year}.zip` containing one PDF per invoice.

**File naming inside ZIP**: `{invoice_number}_{client_code}.pdf`
e.g. `LI-042_AB-1.pdf`

---

## Implementation

### New Code

#### `app/my_practice/views/api_views.py`

Two additions:

1. **`_render_invoice_pdf_bytes(invoice, practice) -> bytes`** — shared helper
   extracted from the existing `invoice_pdf` view. Handles base64 encoding of
   logo/signature, language selection (DE/EN per client), template rendering,
   and WeasyPrint HTML→PDF conversion. Used by both single-invoice and batch
   download.

2. **`invoice_batch_pdf_download(request) -> HttpResponse`** — main view:
   - Reads `year` and `status` from GET/POST params
   - Queries `Invoice.objects.filter(invoice_date__year=year, status=status)`
   - For each invoice calls `_render_invoice_pdf_bytes()`
   - Assembles in-memory `zipfile.ZipFile` using `io.BytesIO` (no disk writes)
   - Returns `application/zip` response with filename `Rechnungen_{year}.zip`
   - Redirects back with a warning message if no invoices found

#### `app/my_practice/urls.py`
```python
path("invoices/batch-pdf/", views.invoice_batch_pdf_download, name="invoice_batch_pdf"),
```

#### `app/my_practice/views/__init__.py`
Exported `invoice_batch_pdf_download`.

### Template Changes

#### `app/templates/my_practice/invoice_list.html`
Download button in the `.actions` bar, shown only when `current_year != 'all'`:
```html
<a href="{% url 'invoice_batch_pdf' %}?year={{ current_year }}&status={{ current_status|default:'paid' }}"
   class="btn btn-outline-secondary btn-sm">
    <i class="bi bi-file-zip"></i> Rechnungen {{ current_year }} herunterladen
</a>
```

#### `app/templates/my_practice/tax_quarter_overview.html`
Download button at the bottom of the tax quarter report:
```html
<a href="{% url 'invoice_batch_pdf' %}?year={{ year }}&status=paid"
   class="btn btn-outline-secondary">
    <i class="bi bi-file-zip"></i> Alle Rechnungen {{ year }} als ZIP herunterladen
</a>
```

---

## Key Design Decisions

- **In-memory only**: ZIP built in `BytesIO`, never touches disk — no cleanup needed.
- **Language-aware**: Uses `client.language` to select DE or EN invoice template,
  consistent with single-invoice download.
- **Shared helper**: `_render_invoice_pdf_bytes()` eliminates duplication between
  single (`invoice_pdf`) and batch view.
- **Status-filtered**: Defaults to `status=paid`; can be overridden via query param.
- **Graceful empty state**: If no invoices match, redirects to the previous page
  with a warning message rather than serving an empty ZIP.

---

## Testing

All 662 existing tests pass. No new test module added (integration tested
manually through the invoice list UI).

---

## Related

- P-014 (or existing `invoice_pdf`): single-invoice PDF, now shares `_render_invoice_pdf_bytes`
- WeasyPrint 63.1 already in `requirements.txt` — no new dependencies
