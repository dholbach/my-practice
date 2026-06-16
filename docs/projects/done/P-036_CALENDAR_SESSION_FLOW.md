# P-036: Calendar → Session Decoupled Flow

**Status**: Done
**Started**: 2026-04-01
**Completed**: 2026-04-01
**Priority**: High (workflow friction)

## Problem

Sessions created by the calendar cron (`fetch_calendar_events`) only become visible in the
client Protokoll tab **after** billing approval — i.e. after the therapist has explicitly
approved the event in `/calendar/approve/`. This means:

- A session that happened today is invisible in the Protokoll tab until the billing step.
- Writing a session log requires a separate navigate-to-approve → approve → back-to-client cycle.
- Log and billing are conceptually separate but get coupled by the approval gate.

## Solution

Decouple `Session` creation from billing. The cron creates the `Session` immediately when a
matched client is found. Billing (InvoiceItem + Invoice) remains a separate step done later.

## Architecture

```
fetch_calendar_events (cron, every few hours)
  ├─ matched client found
  │   ├─ PendingCalendarEvent (status=PENDING)  ← existing
  │   └─ Session.get_or_create(client, date, time)  ← NEW (P-036)
  │       └─ PendingCalendarEvent.session = session  ← NEW FK
  └─ no client match → PendingCalendarEvent only (manual review in /calendar/approve/)

Client Protokoll tab
  ├─ Session with InvoiceItem → normal display
  └─ Session without InvoiceItem → "Unberechnet" badge  ← NEW

Billing approval (unchanged)
  └─ create_invoice_items_from_events() reuses existing Session via get_or_create
```

## Key Design Decisions

- **No new `Session.status` field** — billing status derived from `session.invoice_items.exists()`
- **OneToOne FK** `PendingCalendarEvent.session` — semantic: one event → one session
- **Unmatched clients** stay in queue only — no auto-Session for unknown clients
- **`create_invoice_items_from_events` unchanged** — already uses `Session.get_or_create`, safely reuses pre-created sessions

## Phases

### Phase 1 — Auto-create Sessions on fetch ✅ (2026-04-01)

- [x] `PendingCalendarEvent.session` OneToOne FK (nullable) — `calendar.py`
- [x] Migration `0066_pendingcalendarevent_session`
- [x] `fetch_calendar_events`: auto-create `Session` for matched clients on new events
- [x] `client_detail.html`: "Unberechnet" badge for sessions without InvoiceItems
- [x] CSS: `.cn-session-unbilled` in `client_notes.css`

### Phase 2 — Billing from client detail ✅ (2026-04-01)

- [x] `bill_session(session, practice)` helper in `calendar_import_helpers.py` — determines service type from linked `PendingCalendarEvent.suggested_service_type` (fallback: `therapy_60`), creates `InvoiceItem` + `PracticeTodo`, guards against double-billing
- [x] `session_bill` POST view in `clinical_views.py` — `POST /clients/<pk>/sessions/<session_pk>/bill/`
- [x] URL `session_bill` registered in `urls.py`
- [x] "🧾 Zur Rechnung" button in both session row layouts (with-content + no-content) when `not session.invoice_items.all`
- [x] Exported from `views/__init__.py`

### Phase 3 — /calendar/import/ cleanup (pending)

- [ ] Filter `/calendar/import/` to show only events not yet in DB (reduce list length)
- [ ] Or: retire `/calendar/import/` in favour of `/calendar/approve/` as primary path

## Files Changed (Phase 1 + 2)

| File | Change |
|------|--------|
| `app/my_practice/models/calendar.py` | Added `session` OneToOneField |
| `app/my_practice/migrations/0066_pendingcalendarevent_session.py` | New migration |
| `app/my_practice/management/commands/fetch_calendar_events.py` | Session auto-creation on new matched events |
| `app/my_practice/views/calendar_import_helpers.py` | Added `bill_session()` helper |
| `app/my_practice/views/clinical_views.py` | Added `session_bill` POST view |
| `app/my_practice/views/__init__.py` | Exported `session_bill` |
| `app/my_practice/urls.py` | Registered `session_bill` URL |
| `app/templates/my_practice/client_detail.html` | "Unberechnet" badge + "🧾 Zur Rechnung" button |
| `app/static/css/client_notes.css` | `.cn-session-unbilled` style |
