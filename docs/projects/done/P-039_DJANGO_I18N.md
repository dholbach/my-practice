# P-039: Django i18n — Bilingual App UI

**Status**: DONE (2026-07-20)
**Priority**: Medium
**Depends on**: P-038 ✅, P-024 ✅
**Tracking issue**: [#69](https://github.com/dholbach/my-practice/issues/69) (closed)

## Goal

Make all user-facing UI text translatable via Django's i18n framework so the app
can run in German or English without code changes.

## Outcome

Every template, Python view/form/util, model, `admin.py`, and the small
JS-string surface is wrapped. English msgids throughout; German lives as
`msgstr` in `locale/de/LC_MESSAGES/django.po`. `locale/en/LC_MESSAGES/django.po`
is deliberately left with empty `msgstr` values everywhere — gettext falls back
to the (English) msgid, which is already correct, so there is nothing to fill
in on the English side. Final catalog: 1,846 msgids, 0 fuzzy in either file.

A regression guardrail (`my_practice/tests/test_i18n_coverage.py`, added in
Phase 0) keeps this from rotting: it fails on any non-exempt template missing
`{% load i18n %}`, any leaked raw German text, or any `#, fuzzy` `.po` entry.
The permanent conventions this project established live in the root
`CLAUDE.md` under "i18n Conventions" — that section, not this doc, is the
source of truth for how to write new i18n-correct code going forward.

## How it was done: opportunistic wrapping, then a dedicated sweep

Work started as "wrap templates as you touch them for other reasons"
(scaffold in `feat/i18n-scaffold`, tracked via issue #69). By 2026-07-19 that
opportunistic approach had stalled around 50/86 templates over several
months, with Python-side work (views, forms, models, admin) barely started.
On 2026-07-19 the project switched to a dedicated sweep — six phases, one
area of the codebase at a time, each phase landing as 1-6 PRs with its own
bilingual verification pass. The sweep finished in under two days once
started.

### Phase 0 — guardrail (PR #236)
Added the ratchet test itself. Building it surfaced 3 real regressions in
templates the tracking issue had already marked "done" (partial wrapping,
raw text leaking through `{% include %}` kwargs) — the guardrail earned its
keep before the sweep even began.

### Phase 1 — templates (PRs #237, #238, #239, #240, #242, #243)
All ~84 in-scope templates wrapped, batched by feature cluster (confirm-delete
pages, `includes/` partials, bank review, calendar import/approval,
list/overview views, remainder). 7 templates in the `includes/` cluster and
1 in the remainder cluster turned out to be dead code (never `{% include %}`'d
anywhere) and were deleted rather than translated. `includes/email_card.html`
was marked permanently exempt alongside the pre-existing PDF-template and
`email_utils.py` exemptions — its labels identify bilingual *content*
language, not the app's UI language.

### Phase 2 — Python views (PR #244)
The 7 remaining view files with user-facing strings (`tag_views.py`,
`todo_views.py`, `operational_views.py`, `utils/import_helpers.py`,
`utils/practice_helpers.py`, plus deferred parts of `inquiry_views.py`).
`crud_mixins.py` and `search_views.py` were checked and deliberately skipped
— no real user-facing strings, just docstring examples and data-derived
labels.

### Phase 3 — model verbose_name/help_text (PRs #245, #246, #247)
The largest chunk: ~413 occurrences across 16 model files, split into 3
batches. State-only migrations (verbose_name/help_text/choices never touch
the DB schema — confirmed via `sqlmigrate` on every batch). This phase had
to land before Phase 4 since Django admin inherits field labels from model
verbose_names.

### Phase 4 — admin.py (PR #248)
1,212 lines, zero prior i18n wrapping. Fieldsets, `@admin.display`/
`@admin.action` descriptions, bulk-action messages (`ngettext` for proper
pluralization), and admin site header/title.

### Phase 5 — JS strings (PR #249)
`keyboard-nav.js`, `global-search.js`, `chart_helpers.js` — a small enough
surface (~25 strings) that a full `JavaScriptCatalog` wasn't worth wiring up.
Translated strings are rendered by Django (`{% trans %}`) into `data-*`
attributes on `<body>` in `base.html`; the JS reads them via
`document.body.dataset` at script-load time.

### Phase 6 — close-out (this doc)
A broad bilingual click-through — fetch a spread of real pages under
`Accept-Language: de` and `en` via the Django test client and scan the
*rendered* output for leaked German, not just template source — caught two
more real bugs the guardrail structurally cannot see (below), plus 9
`.po` entries with an empty (non-fuzzy) `msgstr` left over from earlier
phases. `CLAUDE.md` updated from "sweep in progress" to the permanent
steady-state convention; this doc created; `PROJECTS.md`/`FEATURES.md`
updated; issue #69 closed.

## Bugs found along the way (not just missing wrapping)

The sweep repeatedly turned up real localization bugs that predated it —
tracked here because the pattern, not just the individual fix, is worth
remembering:

1. **Unwrapped Python string in a view's context dict.** A template can pass
   the guardrail (has `{% load i18n %}`, no leaked diacritics) while still
   rendering raw German, if a Python view feeds it an unwrapped string that
   happens to contain no umlauts/ß (e.g. `context["action"] = "Erstellen"`).
   Found 3× in different views across Phases 1-2.
2. **ModelForm `Meta.labels`/`label=` shadowing an already-wrapped model
   verbose_name.** Wrapping a model doesn't help if a form overrides the
   field label with raw text — found across `forms.py`, `inquiry_forms.py`.
3. **`_()` called on a German string instead of an English one.** Passes
   every mechanical check (file imports and uses `gettext`) but is wrong —
   `gebueh.py` had this file-wide despite already using `gettext_lazy`
   throughout.
4. **Eager `gettext` used for a class-body/module-level attribute instead of
   `gettext_lazy`.** Freezes the resolved string at process-import time;
   later `translation.override()` calls have no effect. Only a real
   bilingual smoke test (render/instantiate under both locales, assert the
   outputs differ) catches this — code review can't, since it looks
   identical to correctly-wrapped code.
5. **Admin-facing per-record language switch conflated with per-client
   content language.** `calendar_import.html` and `calendar_approval_queue.html`
   always displayed `ServiceType.name_de` regardless of the admin's own UI
   language — found during the Phase 6 click-through. Different from
   `invoice_detail.html`'s (correct) use of `invoice.client.language` to pick
   `name_de`/`name_en`, since that page is client-facing document content,
   not admin UI chrome.
6. **A locale-blind hardcoded month-abbreviation list, reused in three
   places.** `chart_helpers.GERMAN_MONTHS_SHORT` (and an independent
   duplicate, `client_detail_builder._MONTHS_DE`) always returned German
   month abbreviations ("Mär", "Mai", "Okt", "Dez") regardless of active
   locale, feeding the analytics seasonality chart, the `format_month_year`
   template filter, and the client-detail activity-period string. Fixed by
   making the list itself locale-aware (`gettext_lazy`, reusing the msgids
   already established for the analytics page's JS month-label chart) and
   deleting the duplicate. Also caught a fully-unwrapped `f"seit {start_str}"`
   in the same function while fixing it.

## What the guardrail structurally cannot catch

Worth stating plainly for whoever extends this app: `test_i18n_coverage.py`
only scans template *source* for `{% load i18n %}` presence and leaked
diacritics, and scans `.po` files for `#, fuzzy`. It cannot see:

- A Python view/util feeding an already-wrapped template an unwrapped string
  that happens to contain no German-specific characters (bugs #1, #5, #6
  above).
- A `.po` entry with an empty-but-not-fuzzy `msgstr` — `makemessages` only
  marks an entry fuzzy when it has a similarly-worded *existing* msgid to
  guess from; a genuinely novel string gets no guess and no warning at all.
  Found 9 of these left over from earlier phases during Phase 6, plus more
  introduced by Phase 6's own new strings.

Both gaps were only found by periodically rendering real pages under both
locales (via the Django test client, `Accept-Language: de` vs `en`) and
diffing/scanning the actual output — not by strengthening the static
guardrail further. If this app grows enough that manual click-throughs stop
scaling, that's the next thing to automate (e.g. a scheduled job that walks
every named URL under both locales and fails on new diacritic leaks or msgid
divergence), not more regex tightening on the existing test.

## Deliberately out of scope (not bugs)

- **PDF templates** (`invoice_pdf_*.html`, `treatment_contract_pdf.html`,
  `intake_form_pdf.html`, `questionnaire_pdf.html`) — language is
  per-document (the client's language), not Django-i18n UI chrome.
- **`utils/email_utils.py` dual-language content builders** and
  **`includes/email_card.html`** — authored bilingual email content, not
  translatable UI text.
- **`ServiceType.name_de`/`name_en`, `Practice.*_de`/`*_en` fields** used in
  client-facing documents — correctly keyed off the *client's* language, not
  the admin's UI language (see bug #5's contrast above).
- **`models/clinical.py` scaffolding content** (`INTAKE_NOTES_TEMPLATE`,
  `CASE_NOTES_TEMPLATE`, `SESSION_LOG_TEMPLATE`) — authored
  Somatic-Experiencing clinical terminology baked into form `initial=`, no
  English counterpart, not app UI chrome.
- **`ClientTag` names/descriptions and other free-text data fields** —
  data, like a client's name, not translatable UI strings.
- **`TimeOff.TYPE_CHOICES`, `CompanyWithdrawal`/`CompanyExpense`
  `Meta.verbose_name`** — deliberately bilingual by design ("Urlaub /
  Vacation"), shown simultaneously regardless of active UI language.

## Related

- [P-038 Language EN cleanup](P-038_LANGUAGE_EN.md)
- [P-024 OSS Release](P-024_OSS_RELEASE.md)
- Django docs: https://docs.djangoproject.com/en/stable/topics/i18n/
