# P-042: Multi-Practice Tax Allocation

**Status**: ✅ DONE (28. April 2026)
**Priority**: LOW
**Effort**: ~3h total across two sessions
**Completed**: 28. April 2026

---

## What was built

**In-app split calculator** on the tax year summary page (`/tax/year/`):

- When the logged-in user has more than one active practice, a `_PracticeSplitCalc` dataclass is
  computed in `tax_views.py` with two ratio keys for the year:
  - **Revenue key**: this practice's paid revenue ÷ total paid revenue across all active practices
  - **Session-day key**: distinct session days for this practice ÷ total across all active practices
- An allocation table is shown at the top of the page with the resulting split amounts (€) for both
  Home-Office-Pauschale and Entfernungspauschale, one row per key.
- The user picks one key, documents it, and uses it consistently across all EÜR filings.
- For other mixed costs (phone, internet, home workspace): same ratio applies; amounts are entered
  manually as individual expenses in each practice's expense list.

**Implementation**:
- `app/my_practice/views/tax_views.py`: `_PracticeSplitCalc` dataclass, `_compute_practice_split()`
  helper, pre-computed split context vars
- `app/templates/my_practice/tax_year_summary.html`: allocation table block (hidden for single practice)
- `app/static/css/tax_summary.css`: `.allocation-note`, `.allocation-split-table` styles
- 13/13 tax view tests pass (including `test_practice_split_computes_ratios`,
  `test_practice_split_is_none_for_single_practice`)

**Session 2 additions** (commit `35e54b6`):

- `TaxYearNote` model: practice+year-scoped free-text note for documenting the chosen split key;
  saved via AJAX widget in the tax summary page (upsert endpoint `save_tax_year_note`)
- `WorkdayAuditCalculator` + `DayAuditEntry` / `WorkdayAuditResult` in `practice_days.py`:
  classifies every Mon–Fri in a year as `practice`, `home_office`, `holiday`, or `timeoff`;
  uses Berlin public holiday names; counts sessions per day from the DB
- `tax_workday_audit` view + `tax_workday_audit.html` template: printable day-by-day audit page
  with per-day badge, summary stat boxes, year selector, and `@media print` styling
- `app/static/css/tax_workday_audit.css`: dedicated stylesheet for the audit page
- `app/static/css/tax_summary.css`: `.tax-note-widget` + `.audit-link-row` styles
- 21/21 tax view tests pass (8 new tests for note and audit)

---

## Problem

Home-office and commute pauschalen are daily lump sums — per calendar day, each may only be claimed
once across all self-employed activities. A practitioner running both a therapy practice and a
coaching practice needs a documented split key to avoid double-claiming in separate EÜR filings.

---

## Core tax rule

- Per calendar day, each daily pauschale (HO: 6.00 €/day; commute: km × rate) can only be claimed
  once in total across all activities.
- If multiple activities happened on the same day, split the daily amount using a consistent,
  documented key.

Recommended keys (choose one and keep it consistent):

- **Time-based**: hours per activity on that day
- **Revenue ratio**: annual revenue share per practice (good for low-materiality mixed days)
- **Session-day ratio**: session days per practice in the year

## Examples

### Home-office day

- Daily pauschale = 6.00 EUR (single day total)
- Mixed day: therapy 3h, coaching 2h → therapy gets 3/5, coaching gets 2/5

### Practice commute day

- Single commute deduction for the day (for example: 8 km × 0.30 EUR = 2.40 EUR)
- If both activities use that commute day, split the day amount with the same key

## Documentation expectations

- Keep a short note with the chosen key (for example: "Allocation based on annual revenue ratio 95/5").
- Keep day-level evidence ready (calendar, session logs, invoices) for follow-up questions.
- Do not submit full day lists unless requested, but keep them audit-ready.
