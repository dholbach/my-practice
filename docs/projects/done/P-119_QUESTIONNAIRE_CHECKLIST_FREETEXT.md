# P-119: Checklist + freetext block types for questionnaire PDFs

Follow-up to [P-118](P-118_QUESTIONNAIRE_PDFS.md), which shipped the
clinical-questionnaire PDF pipeline with a single block type (`grid`) and
one instrument (GAD-7). This adds the two remaining block types needed for
ADNM-20 and similar multi-part instruments:

- **`checklist`** — statement rows with a single yes/no checkbox, no
  response scale (ADNM-20 part 1: 18 life events).
- **`freetext`** — a prompt with N blank fillable lines (ADNM-20's "please
  indicate the most straining event(s)").

Both render as real AcroForm fields via WeasyPrint's `pdf_forms=True`, same
as the `grid` type's radio buttons.

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

## Deliberately not done

ADNM-20 part 2 needs two *independent* column groups per statement
(frequency **and** duration side by side) — the `grid` type only supports
one column group per item. Not extended here since it wasn't part of what
was asked for. Workaround once ADNM-20's content file is built: represent
part 2 as two separate `grid` sections (frequency, then duration), each
repeating the item labels — lower-fidelity than the source form, fully
functional with no new code. If full fidelity is wanted later, `grid` would
need a `column_groups` variant.

No ADNM-20 content file shipped in this PR — that's licensed content
Daniel sources himself and drops into
`PAYMENTS_DATA_DIR/questionnaires/adnm20.json` (never committed, per the
P-118 licensing boundary).
