# P-006: Clinical documentation that stays up to date

**Status**: TODO (spec)
**Priority**: High
**Estimated effort**: six PRs, from a few hours (PR 1) to several days (PR 4)
**Created**: 2026-11-25

---

## Goal

Make the clinical part of the client page something the therapist keeps up to date without effort, and enjoys
using. Insights from sessions should reach the case formulation through small, quick steps, so keeping it current
no longer depends on finding a block of focus time.

## Why: what gets in the way today

- **The clinical view is split across tabs.** The overview, the profile fields and the session protocol live on
  different tabs, so preparing a session means jumping between them. The profile is edited in large textareas
  that are awkward to write in.
- **Session insights and the case formulation are disconnected.** Session logs and notes are dated and
  append-only. `ClientProfile.intake_notes` / `case_notes` are single markdown blobs (about 22 headings in one
  textarea), undated and unsourced. Each save overwrites them, with no history. Something learned in a session
  only reaches them through a separate manual edit, so they tend to fall behind.
- **Updating the case formulation takes a dedicated block of time.** Reviewing several sessions means gathering
  them by hand first. The app does none of that setup.
- **The log form is heavier than needed.** It has six text fields, and the prefilled template inserts large
  headings that are usually deleted. The one-liner and the session note are the core; the rest is optional.
- **Looking back means scrolling.** The notes are Fernet-encrypted, so there is no server-side search, and only
  the first 10 entries are visible.
- **Quick reminders have no place.** A short "next time with XX-1: ask about …" has no lightweight home, so such
  notes end up outside the app.
- **The structure lost fields.** The original template was a compact two-column table with the case on top and
  dated sessions below, in one document. Moving it into markdown lost that layout and some fields: *Dauer bis*,
  *Loyalität/Scham/Schuld*, *Mentalisationsgrad* and SIBAM *fehlend*. The template also has both an
  `## Arbeitsdiagnose` heading and a separate `arbeitsdiagnose` field.

## Principles

1. **One clinical page.** Case sheet on top, sessions below, in one scroll. Billing and admin are a separate
   mode, out of sight while working clinically.
2. **Small digests over big rituals.** Every step that moves an insight into the case sheet is optional, one
   line, and possible from where you already are.
3. **Make the deliberate review cheap.** The app does the setup: only what is new since the last review, next to
   the sheet.
4. **Invite, don't nag.** No "stale for N months" alarms. Offer "6 sessions since your last review" instead, and
   show empty fields as a hint, never as a warning.
5. **Nothing is lost.** Case sheet lines are dated and sourced, and they are superseded rather than overwritten.
   Check whether § 630f BGB (corrections must leave the original and the date of change visible) applies to
   this practice type. If it does, it also covers edits to session logs.
6. **The existing guardrails still apply.** Practice scoping fails closed, everything narrative is encrypted,
   privacy mode, i18n, CSP-safe Alpine.

## Plan

Each PR is useful on its own. 1–3 need no new clinical data model; 5 and 6 build on 4.

### PR 1: A lighter log form with context beside it

- The template's headings become **prompt chips** above the session note (Gefühl danach, Wahrnehmung, Sitzung,
  Was half). Clicking one inserts it, and nothing is prefilled that has to be deleted.
- One-liner and session note up front. Interventions, ideas for next time and the supervision question go
  behind "More", which opens automatically when any of them has content.
- **Own reflection stays a separate field** (decided 2026-11-25), so that an export, if one is ever required,
  can leave countertransference out and stay neutral. It sits right below the session note as a small field.
  A "Wie ging es mir dabei" chip writes its prompt into that field and focuses it, as a nudge. A field left
  holding only a prompt is saved as empty.
- **Context panel** beside the form: last session's ideas for next time, the last 3 one-liners, and an excerpt
  of the case formulation (hypothesis, current triggers, resources).
- *Why:* the log is where the work happens already. Showing the open threads there costs nothing and addresses
  the "where did we leave off" scroll.

### PR 2: "For next time" and a scratchpad

- New `ScratchItem(TimestampedModel)`: client, encrypted text (max 300 characters), `done_at`. Practice
  scoped through its client and deleted with it (GDPR delete). `source_session` is left out until PR 5 creates
  items from a log.
- A "For next time" card at the top of the clinical page and in the log form's context panel. It merges open
  scratch items, last session's ideas and the case notes' future-work list. Items can be ticked as covered;
  unticked ones carry over.
- Open reminders are also checkboxes in the log form's side panel (new log and edit alike); saving the log marks
  the ticked ones covered. The panel also has a field for new reminders, one per line, created on save, so a
  reminder can be added where the work happens without leaving the form.
- Reminders can be reworded (✎ on the client page, an editable field in the log form, saved with the log). A
  reminder ticked in a log records `covered_in_session`, so covered ones show their date as a link to that log;
  ticking on the client page records no session. The card folds the covered ones away; the log form lists the last 5.
- **Follow-up (PR 2b):** capture from anywhere through the command palette (P-047), e.g. "note XX-1 ask about
  sleep". It needs a command mode in `command_palette.js` (today every entry is a plain link), so it is its own PR.
- *Why:* gives quick reminders a home that is as fast as a note on paper and shows up at the right moment.

### PR 3: One clinical page, and session search

Split in two: **3a** (the Clinical / Admin modes) and **3b** (timeline layout and search).

- **3a:** the client page gets a **Clinical / Admin** switch. Clinical: "For next time", the case formulation (still
  the current fields until PR 4), and the session timeline in one scroll. Admin: contact, billing, invoices and
  onboarding. Assessments and documents follow the timeline in the clinical mode; contact and the source
  inquiry sit with onboarding in the admin mode. The overview's recent-sessions card is dropped (the timeline is
  right below), and a slim intake hint links to the admin mode while onboarding is open.
- **3b (built):** timeline rows follow the original template's layout: date, type and interventions in the left column; one-liner and
  tags on the right; the note folds open.
- **3b:** search across all entries, older ones included. Done in the browser over decrypted, server-rendered
  entries, since a client has at most a few hundred.
- *Why:* removes the tab-jumping, and finding something no longer means scrolling.

### PR 4: The case sheet (ClinicalFact)

As built (migrations 0018 and 0019):

- New `ClinicalFact(TimestampedModel)` in `models/case_sheet.py`: client, `kind` (the row) and `sub` (the
  cell), encrypted `content`, `noted_on`, optional `source_session`, `status` (`active` / `superseded` /
  `resolved`), `closed_on` and `superseded_by`. The rows are defined in code (`CASE_SHEET_ROWS`), not as model
  choices, so adding or renaming one needs no migration. `source_note` was dropped: nothing creates a line
  from a note yet.
- Rows follow the old intake form: Anliegen, Symptomatik (Beginn | Verschlimmerung / Änderung | Dauer bis),
  Körperlich, Affektiv, Erst-Auslöser, Akt. Trigger, Anamnestische Besonderheiten, Nervensystem / ANS,
  Limbisches System (Nähe-/Distanzmuster | Empathiefähigkeit | Loyalität / Scham / Schuld), Neocortical
  (Präsenz / Fokusstabilität | Mentalisationsgrad), Glaubenssätze, SIBAM (bevorzugt | fehlend), Ressourcen,
  Arbeitshypothese, Arbeitsdiagnose, Therapieziel, „Sicherheit“ gestört durch, Prozessaufbau, O-Töne (the
  client's own phrases), Themen, Familiendynamik, Ich-Du, Herausforderungen, Zukünftige Arbeit / Fragen, and
  "Weitere Notizen" for text that fits no row. *Multi* rows (triggers, resources, beliefs, themes …) hold
  several current lines; the others hold one, which a new line supersedes.
- The **case sheet** is a compact table on the client page's clinical mode, replacing the intake / case notes
  textareas: label column, sub-cells side by side, every line dated, a line added from a log linking to it.
  A line is added (＋), reworded (✎: the new wording is a new line, the old one is superseded and stays under
  "earlier lines") or marked "no longer applies". Nothing is overwritten or deleted.
- **Migration 0019** splits each profile's `intake_notes` / `case_notes` by `## ` heading into lines dated
  with the profile's last save: labelled values (`**Beginn:** …`) go to their cells, bullet lists in a multi
  row become one line per bullet, and anything that matches no row (an unknown heading, text before the first
  heading, the old "Verlauf" section) goes to "Weitere Notizen" with its heading. The `arbeitsdiagnose` field
  becomes the diagnosis line and wins over the intake section's text, which is kept as a note when it differs.
  A client who already has lines is skipped, so running it again duplicates nothing.
- The old fields stay in the database and show read-only under "Previous notes" until you have checked the
  split on real data. Retiring them (fields, the section in the page) is a follow-up once that is confirmed.
- The working diagnosis (invoices, the header, the stat card, the missing-diagnosis callout) is the diagnosis
  row's current line. The log form's side panel and "For next time" read the sheet as well.
- Row and cell labels are authored German vocabulary (the same i18n exemption as the old template). Other
  self-hosters can't change the rows yet; per-practice rows remain an open question.
- *Why:* gives the case formulation dates, sources and history, and makes the small digests of PR 5 possible.
  This is the change that addresses the root cause.

### PR 5: "Anything for the case sheet?"

As built:

- Saving a **new** log redirects to the client page with `?digest=<session pk>#digest-card`. A card above the
  timeline names the session, lists the lines already added from it, and has a picker (every cell of the
  sheet; a single-line cell that already has a current line says it replaces it), a line field and **Add**.
  Adding returns to the same card, so several lines can follow one another; **Nothing today** / **Done** is a
  plain link to the client page. Skipping costs one click, or none: the card sits on the page you land on.
- The line becomes a `ClinicalFact` with the session as its source (`case_fact_add` takes a `target` of
  "kind|sub" and a `source_session`, which has to be one of the client's sessions, else it is ignored), and
  shows on the sheet with a link to that log.
- Every logged session row has a **Case sheet** button that opens the same card for it later ("send a line to
  the case sheet" from any timeline entry). Editing a log does not open the card by itself.
- No JavaScript and no new model: the card is server-rendered from the query string.
- *Why:* most digesting happens here, in seconds, while the session is fresh.

### PR 6: Review

- New `CaseReview(TimestampedModel)`: client, `reviewed_on`, optional encrypted note.
- A **Review** view: the sessions and notes since the last review on one side, each line with a "→ row" action;
  on the other side the changes collected so far, the hypothesis with its earlier versions, "then and now"
  (early vs recent *In their words*), still-empty fields (as a hint), and open supervision questions.
  "Finish review" records the `CaseReview`.
- The timeline shows "Reviewed on …" markers. The clinical page offers "N sessions since your last review" once
  there are a few. A Focus Queue (P-050) signal is optional and gently worded.
- *Why:* the deliberate review becomes cheap to start and good for supervision prep, and seeing a case move is
  the rewarding part.

## Open questions

- **Rows:** are the template's rows still the right ones, or should some be merged or dropped?
- **§ 630f BGB:** does it apply, and does it require history for session log edits too?
- **Practice types:** is the SE-specific row set a per-practice configuration, so other self-hosters can use
  their own?

## Out of scope (for now)

- **AI assistance.** An optional, strictly local model (no cloud API) could later suggest facts from a new log,
  prepare a pre-session brief, or answer cited questions about a case's history. It would only ever propose;
  nothing is written without the therapist accepting it. It depends on PR 4–6 and is a separate project.
- Changes to billing, invoicing or onboarding beyond moving them to the Admin view.
