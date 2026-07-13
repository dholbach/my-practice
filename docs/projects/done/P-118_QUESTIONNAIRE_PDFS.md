# P-118: Clinical Questionnaire PDFs (send-only pilot)

## Goal

Replace ad hoc `.odt`/`.doc`/`.xls` clinical questionnaires with branded,
fillable PDFs (DE/EN) that look and behave like the existing intake form /
treatment contract PDFs, and can be sent to a client with the same one-click
flow already used for those documents.

## Key design decision: content/template separation

Two of the instruments therapists commonly use (BDI-II, ADNM-20) are
copyrighted — BDI-II commercially (Pearson), ADNM-20 by its authors. This
repo is public on GitHub, so their item text must never enter git history.

The rendering template (`questionnaire_pdf.html`, committed) only defines a
generic branded shell + a `grid` block layout (statement rows × response
columns). The actual question text lives in a JSON content file, loaded at
render time via `utils/questionnaire_content.py`:
- Instance-local first: `MY_PRACTICE_DATA_DIR/questionnaires/<code>.json`
  (never committed — same convention already used for the `Anamnesebogen.docx`
  attachment in `SendQuestionnaireEmailView`)
- Falls back to `app/my_practice/questionnaire_content/<code>.json` shipped
  in-repo, for public-domain instruments only

This means every instrument gets the same branded/fillable treatment
regardless of licensing status — adding BDI-II or ADNM-20 later is a matter
of dropping a content file under `MY_PRACTICE_DATA_DIR/questionnaires/`, not
writing new code.

## What shipped

- `generate_questionnaire_pdf_bytes(code, practice, lang)` — renders a
  client-agnostic, fillable PDF via WeasyPrint's `pdf_forms=True` (real
  AcroForm radio buttons, not just visual boxes)
- One flagship instrument fully wired end-to-end: **GAD-7** (public domain,
  Pfizer-released), shipped as an in-repo content file
- `questionnaire_pdf` view — direct preview/download, `?lang=` switch
- `SendQuestionnairePdfEmailView` — reuses the existing `BaseClientEmailView`
  scaffolding (same class as `SendContractEmailView`/`SendIntakeFormEmailView`)
- "Assessments" card on the client detail page (standalone, not part of the
  one-time onboarding stepper — this is a periodic send, not a one-off intake
  step)

## Deliberately deferred

- **More instruments** (ADNM-20, BDI-II, PHQ-9, etc.) — the mechanism
  supports them; only a content file is needed per instrument once sourced
  and license-checked. tomedo's [Lizenzfreie Fragebögen](https://support.tomedo.de/handbuch/tomedo/fachgruppen/psychotherapie/lizenzfreie-frageboegen/)
  list is a useful source for other likely-safe candidates, but each still
  needs individual verification before its text is committed to git.
- **Completed forms coming back into the app** (e.g. as a `ClientDocument`) —
  a distinct feature with its own DPIA implication (storage counts as
  processing under GDPR even if the app never reads the content). Sending a
  *blank* form doesn't touch client-specific psychological data, so no DPIA
  change was needed for this pilot.
- **`checklist` and `freetext` block types** — named in the content schema
  but not implemented; only `grid` was needed for GAD-7. Implemented in
  [P-119](P-119_QUESTIONNAIRE_CHECKLIST_FREETEXT.md).
