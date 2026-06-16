# P-041 — Monthly Batch Invoicing

**Status**: Done
**Completed**: April 2026

---

## Goal

Replace the "check open invoices, figure out what's ready" loop with a single
monthly batch view: at month-end, open `/invoices/batch/`, review one card per
client with all their unbilled sessions, select all, hit Generate — done.

## What was built

- `GET /invoices/batch/?ym=YYYY-M` — month picker (data-driven: only months with
  unbilled sessions appear), one card per client showing session dates, durations,
  and subtotal preview; all pre-selected
- `POST /invoices/batch/` — creates one DRAFT Invoice + InvoiceItems per selected
  client; redirects to invoice list filtered to new drafts
- ServiceType auto-selected from session duration (≥90 → therapy_90, else therapy_60)
- 20-min intro calls (duration ≤ 20) excluded from the view and the month dropdown
- `fetch_calendar_events` auto-skips `therapy_free` events in the approval queue
  (Session still auto-created for protocol tab)
- Button added to `/invoices/` list page

## Files

- `app/my_practice/views/batch_invoice_views.py` (new)
- `app/templates/my_practice/batch_invoice.html` (new)
- `app/static/css/batch_invoice.css` (new)
- `app/my_practice/urls.py` — added `invoices/batch/`
- `app/my_practice/views/__init__.py` — export + `__all__`
- `app/templates/my_practice/invoice_list.html` — Monatsabrechnung button
- `app/my_practice/management/commands/fetch_calendar_events.py` — auto-skip free sessions
