# P-100 — Complexity Reduction (Radon Hotspots)

**Status**: DONE (7/7 — 2026-05-11)
**Priority**: Medium
**Created**: May 2026

---

## Goal

Reduce cyclomatic complexity in the biggest hotspots identified by `radon cc`. The aim
is not zero complexity — large views will always have some — but to extract reusable
helpers so individual functions stay below D (complexity 20) and are easier to test.

Current baseline from `./dev.py review --full` (2026-05-04):

| Complexity | File / symbol |
|-----------|---------------|
| ~~E (40)~~ → **A (1)** ✅ | `views/client_views.py` — `client_detail` → extracted `ClientDetailContextBuilder` (2026-05-11) |
| ~~D (26)~~ → **C (15)** ✅ | `utils/calendar_import_helpers.py` — `create_invoice_items_from_events` → extracted `_resolve_client/service_type/rate`; `bill_session` C(18)→C(12) as a side effect (2026-05-11) |
| ~~E (36)~~ → **B** ✅ | `views/calendar_views.py` — `calendar_import` → `CalendarImportProcessor` (2026-05-11) |
| ~~E (31)~~ → **B** ✅ | `commands/fetch_calendar_events.py` — `_fetch_for_practice` → 5 private helpers (2026-05-11) |
| ~~D (30)~~ → **A** ✅ | `utils/practice_analysis.py` — `generate_insights` → 4 topic methods (2026-05-11) |
| ~~D (27)~~ → **A (1)** ✅ | `views/dashboard_views.py` — `dashboard` → `DashboardContextAssembler` (2026-05-11) |
| ~~D (26)~~ → **C (15)** ✅ | `utils/calendar_import_helpers.py` — `create_invoice_items_from_events` → extracted `_resolve_client/service_type/rate`; `bill_session` C(18)→C(12) as a side effect (2026-05-11) |
| ~~D (24)~~ → **A (1)** ✅ | `views/tax_views.py` — `tax_year_summary` → `TaxYearContextBuilder` (2026-05-11) |
| ~~D (23)~~ → **B** ✅ | `views/calendar_views.py` — `calendar_import_events` → `CalendarImportProcessor` (2026-05-11) |

Management commands that are run-once / rarely touched (`remove_financial_duplicates`,
`import_session_odt`, `bank_import.py`) are lower priority and excluded from this scope.

---

## Approach per hotspot

### 1. `client_detail` — E (40) — highest value

Extract a `ClientDetailContextBuilder` (same pattern as `AnalyticsDashboardBuilder`).
Group the existing local-import-heavy blocks into builder methods:
- `_build_stats()` — revenue, session count, avg duration, activity period
- `_build_clinical_context()` — sessions_qs, logs, notes, supervision
- `_build_billing_context()` — open invoices, reminder urgency, unbilled sessions

The view becomes ~30 lines: instantiate builder, call `.build()`, return render.

### 2. `dashboard` — D (27)

Already has `DashboardWidgetBuilder` and friends; the function itself still assembles
too much inline. Extract a `DashboardContextAssembler` that owns the widget list and
preflight results, leaving the view function as a thin wrapper.

### 3. `calendar_import` + `calendar_import_events` — E (36) / D (23)

Both live in `calendar_views.py`. The import logic mixes HTTP concerns (form parsing,
messages, redirect) with business logic (matching, session creation, de-duplication).
Extract a `CalendarImportProcessor` to `utils/calendar_import_helpers.py` that owns
the business logic; views call it and handle the HTTP layer only.

### 4. `create_invoice_items_from_events` — D (26)

Already in utils; the D rating comes from nested conditionals around rate/service-type
resolution. Extract `_resolve_service_type(event)` and `_resolve_rate(client, service_type)`
as private helpers; the main function becomes a loop over the resolved values.

### 5. `tax_year_summary` — D (24)

Extract a `TaxYearContextBuilder` parallel to existing `FinancialListContextBuilder`.
The view becomes a thin wrapper; the builder can be unit-tested independently.

### 6. `PracticeAnalyzer.generate_insights` — D (30)

Split the monolithic `generate_insights` into topic-scoped methods:
`_revenue_insights()`, `_capacity_insights()`, `_client_churn_insights()`. The public
method becomes a list-concat of the three.

### 7. `fetch_calendar_events._fetch_for_practice` — E (31)

Management command, but touched monthly. Extract a `CalendarEventFetcher` class with
methods for matching, deduplication, and session auto-creation. Mirrors the pattern in
`calendar_import_helpers.py`.

---

## Suggested order

1. `client_detail` — touched every session, highest E, clear builder pattern available
2. `create_invoice_items_from_events` — billing core, easy sub-function extraction
3. `tax_year_summary` — monthly use, builder pattern straightforward
4. `dashboard` — daily use, already partially decomposed
5. Remaining (calendar, practice_analysis, fetch_calendar_events) — lower ROI per hour

---

## Success criteria

- All listed symbols below D (< 20) after refactor
- No new behaviour: all existing tests pass, no template changes
- Each builder/processor has its own unit tests covering the extracted logic
