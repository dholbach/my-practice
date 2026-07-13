# P-119: Checklist + freetext block types for questionnaire PDFs

Follow-up to [P-118](P-118_QUESTIONNAIRE_PDFS.md), which shipped the
clinical-questionnaire PDF pipeline with a single block type (`grid`) and
one instrument (GAD-7). This adds the two remaining block types needed for
ADNM-20 and similar multi-part instruments:

- **`checklist`** — statement rows with a single yes/no checkbox, no
  response scale (ADNM-20 part 1: 18 life events).
- **`freetext`** — a prompt with N blank fillable lines (ADNM-20's "please
  indicate the most straining event(s)").
- **`grid` with `column_groups`** — two (or more) independent response
  scales per statement, side by side (ADNM-20 part 2: "frequency" and
  "duration" per statement, matching the source form's layout rather than
  splitting into two separate tables).

All render as real AcroForm fields via WeasyPrint's `pdf_forms=True`, same
as the original `grid` type's radio buttons.

## What changed

- `api_views._resolve_questionnaire_section(section, lang, index)` — new
  per-type resolver, replacing the old grid-only list comprehension in
  `generate_questionnaire_pdf_bytes`. Every section is now resolved (not
  silently filtered); an unrecognized `type` raises `ValueError` instead of
  quietly vanishing from the PDF.
- **Field-naming collision fix**: AcroForm field names are now prefixed by
  section index (`s{i}_q{j}`, `s{i}_c{j}`, `s{i}_f{j}`) so a document mixing
  multiple sections never produces colliding field names. This renamed
  GAD-7's existing fields from `q1`..`q7` to `s0_q0`..`s0_q6` — an internal
  AcroForm field-name change only, nothing user-visible.
- `questionnaire_pdf.html` gained `checklist` and `freetext` branches, plus
  an optional per-section `intro` (any section type can now have its own
  intro text, not just the document-level one).
- `grid` sections can now specify `column_groups` (a list of
  `{label, columns}`) instead of a flat `columns` list — renders a two-tier
  header (group label spanning its columns, then individual column labels)
  and, per statement row, one independent radio group per column group
  (`s{i}_q{j}_g{k}`). Backward compatible: existing flat-`columns` grids
  (GAD-7) are unaffected.

Chose to build the full two-scale grid rather than the "two separate tables"
workaround floated when P-118 shipped — a client filling out a real
20-statement instrument shouldn't have to answer the same 20 statements
twice in disconnected tables; the extra code is a reusable primitive for any
future instrument with the same multi-scale-per-item shape, not a one-off
ADNM-20 hack.

No ADNM-20 content file shipped in this PR — that's licensed content
Daniel sources himself and drops into
`MY_PRACTICE_DATA_DIR/questionnaires/adnm20.json` (never committed, per the
P-118 licensing boundary).
