# P-035 — Session-Centric Calculations

**Status:** DONE — all follow-up items resolved (2026-04-02)  
**Priority:** Medium  
**Estimated effort:** ~4–6h

## Completed

### Phase 1 ✅ — Schema + backfill migration
- `Session.cancelled` (BooleanField, default False, db_index)
- `Session.group_size` (PositiveSmallIntegerField, default 1)
- Migration 0065 with data backfill from InvoiceItems

### Phase 2 ✅ — Core calculations rewritten
- `count_session_hours()` added to `calculations.py` — pure Session-based path
- `capacity_helpers._get_booked_hours()` — filters `session__cancelled=False`
- `capacity_helpers.get_capacity_trends()` — filters `session__cancelled=False`, uses
  `session__group_size` at DB level (also fixed latent bug: cancellations were previously
  not excluded in the DB aggregation path)
- `dashboard_widgets.ClientAttentionWidgetBuilder` — queries `Session` directly

### Phase 3 ✅ — Lifecycle wiring
- `signals.py` — `post_save`/`post_delete` on InvoiceItem syncs `session.cancelled`
  and `session.group_size` via `_resync_session()`. All InvoiceItem saves (form, admin,
  calendar import) automatically keep Session in sync.
- `Session.cancelled` + `group_size` in admin list_display and list_filter
- `InvoiceCSVImporter` identified as dead code and removed

## Remaining follow-up

`report_monthly_sessions.py` standalone script — last usage of `"Ausfall" not in item.description`; use `item.session.cancelled` instead.

~~Still using `"Ausfall" in description` pattern (non-blocking; signal keeps data in sync):~~

| Location | Notes |
|---|---|
| ~~`analytics_utils.py` L210, 228, 241~~ | ✅ Done — uses `session__cancelled=False` |
| ~~`dashboard_widgets.py` `CapacityMonitoringWidgetBuilder._get_month_stats`~~ | ✅ Done — uses `session__cancelled=False` |
| ~~`client_views.py`, `client_helpers.py`~~ | ✅ Done — uses `session.cancelled` |
| `report_monthly_sessions.py` | ✅ Fixed 2026-04-02 — switched to `not item.session.cancelled` |

**Intentionally kept description-based** (billing/revenue domain, out of scope):
- `count_sessions()` — InvoiceItem billing calculations
- `revenue_helpers.py` — revenue excluding cancellations


## Goal

Move all capacity/analytics calculations from `InvoiceItem`-based queries to `Session`-based queries.
`Session` becomes the source of truth for "did a clinical encounter happen";
`InvoiceItem` stays as the billing record only.

## Background

Currently, every analytics calculation (capacity tracking, session counting, busiest months,
client attention widget) filters `InvoiceItem` objects and traverses to `Session` for dates/duration.
This creates an implicit dependency: a Session without an InvoiceItem is invisible to analytics,
and a Session's clinical status (cancelled vs. happened) is encoded in `InvoiceItem.description`
as a substring match (`"Ausfall" in item.description`).

`duration` already lives on `Session`. The missing pieces are:
- a first-class `cancelled` flag
- `group_size` (currently only on `InvoiceItem`, but it is a clinical fact: group vs. individual)

Note: `InvoiceCSVImporter` is defined but **not wired to any view** — it is effectively dead code and
does not need to be considered here. The only active CSV importer is `BankStatementImporter`
(bank statements → `Invoice.paid` status), which is entirely unrelated to Sessions.

## Target architecture

```
Session  ──has──  InvoiceItem (billing record)
         ──has──  SessionLog  (clinical notes)

Session.cancelled  →  replaces "Ausfall" in InvoiceItem.description check
Session.group_size →  replaces InvoiceItem.group_size in therapist-hour calculations
```

Valid Session states after migration:

| InvoiceItem | SessionLog | Meaning |
|---|---|---|
| ✅ | ✅ | Billed + documented (standard) |
| ✅ | — | Billed, not yet documented |
| — | ✅ | Documented (clinical log), not yet billed |
| — | — | Calendar placeholder / in-progress |

Sessions without an InvoiceItem become **first-class valid state**, not orphans.

## Scope

### Out of scope (stays InvoiceItem-based)
- Revenue calculations (`RevenueCalculator`, `Invoice.total`, `InvoiceItem.rate/total`)
- Invoice PDF generation
- Bank statement import (`BankStatementImporter`)

### In scope

#### Phase 1 — Schema + backfill migration
- Add `Session.cancelled` (`BooleanField`, default `False`)
- Add `Session.group_size` (`PositiveSmallIntegerField`, default `1`)
- Data migration: backfill from linked InvoiceItems
  - `session.cancelled = True` where any linked item has `"Ausfall"` in `description`
  - `session.group_size = item.group_size` from the linked InvoiceItem (if exists)

#### Phase 2 — Rewrite calculations

Files to update:

| File | What changes |
|---|---|
| `utils/calculations.py` — `count_sessions()` | Accept `Session` queryset; derive hours from `session.duration × session.group_size`; filter `session.cancelled` |
| `utils/capacity_helpers.py` — `_get_booked_hours()` | Query `Session.objects.filter(session_date__range=..., cancelled=False)` directly |
| `utils/capacity_helpers.py` — `get_capacity_trends()` | Same; fixes latent bug where cancellations were not excluded at DB level |
| `utils/analytics_utils.py` — `SessionAnalyzer.get_busiest_months()` | Port to Session queryset |
| `utils/analytics_utils.py` — `SessionAnalyzer.get_type_distribution()` | Port to Session queryset; use `session.duration` instead of description parsing |
| `utils/dashboard_widgets.py` — client attention widget | Update "last session" query to use `Session.session_date` directly |

`count_sessions()` callers that pass `InvoiceItem` querysets need to be audited and updated.

#### Phase 3 — Lifecycle wiring
- In invoice form save (`InvoiceCreateView`, `InvoiceEditView`): when an item with `"Ausfall"` in
  description is saved, set `item.session.cancelled = True`
- In `calendar_import_helpers.py`: respect `cancelled` flag if calendar event carries cancellation
  signal
- Add `Session.cancelled` to admin list display for visibility

## Migration notes

- Backfill query for `cancelled`:
  ```sql
  UPDATE session SET cancelled = TRUE
  WHERE id IN (
      SELECT DISTINCT session_id FROM invoiceitem WHERE description ILIKE '%Ausfall%'
  );
  ```
- Backfill for `group_size`: take `MAX(group_size)` per session (multiple items per session are rare
  but possible via CSV import)
- After migration, keep `InvoiceItem.group_size` for billing calculations (therapist revenue split)
  but stop reading it for capacity analytics

## Risks / open questions

- `count_sessions()` is called in several places with InvoiceItem querysets — need full audit before
  changing its signature (or create a new `count_session_hours()` alongside and migrate callers)
- `InvoiceCSVImporter` creates Sessions with `invoice_date` as proxy for `session_date` — dates are
  approximate. This pre-existing issue is not fixed by this migration but orphan accumulation stops
  being a problem once Session-with-no-InvoiceItem is a valid state.
- Calendar sync: currently no code deletes Sessions when a Google Calendar event is removed — that
  remains unchanged. Stale `calendar_event_id` is tolerable.
