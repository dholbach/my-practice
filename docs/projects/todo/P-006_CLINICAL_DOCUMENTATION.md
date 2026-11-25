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
- Open reminders are also checkboxes in the log form's side panel; saving the log marks the ticked ones covered.
- **Follow-up (PR 2b):** capture from anywhere through the command palette (P-047), e.g. "note XX-1 ask about
  sleep". It needs a command mode in `command_palette.js` (today every entry is a plain link), so it is its own PR.
- *Why:* gives quick reminders a home that is as fast as a note on paper and shows up at the right moment.

### PR 3: One clinical page, and session search

- The client page gets a **Clinical / Admin** switch. Clinical: "For next time", the case formulation (still
  the current fields until PR 4), and the session timeline in one scroll. Admin: contact, billing, invoices and
  onboarding.
- Timeline rows follow the original template's layout: date, type and interventions in the left column; one-liner and
  tags on the right; the note folds open.
- **Search** across all entries, older ones included. Done in the browser over decrypted, server-rendered
  entries, since a client has at most a few hundred.
- *Why:* removes the tab-jumping, and finding something no longer means scrolling.

### PR 4: The case sheet (ClinicalFact)

- New `ClinicalFact(TimestampedModel)`: client, `kind` (one per row of the case sheet, see below), optional
  `sub` (sub-cell, e.g. *Beginn*), encrypted `content`, `noted_on`, optional `source_session` / `source_note`,
  `status` (`active` / `resolved` / `superseded`) and `superseded_by`.
- Rows: Anliegen, Symptomatik (Beginn | Verschlimmerung/Änderung | Dauer bis), Körperlich, Affektiv,
  Erst-Auslöser, Akt. Trigger, Anamnestische Besonderheiten, Nervensystem/ANS, Limbisches System
  (Nähe/Distanz | Empathie | Loyalität/Scham/Schuld), Neocortical (Präsenz/Fokus | Mentalisationsgrad),
  Glaubenssätze, SIBAM (bevorzugt | fehlend), Ressourcen, Arbeitshypothese, Arbeitsdiagnose, Therapieziel,
  „Sicherheit“ gestört durch, Prozessaufbau, *In their words* (the client's own phrases). Case-note lists:
  Themen, Familiendynamik, Ich-Du, Herausforderungen, Zukünftige Arbeit/Fragen.
- The **case sheet** renders as a compact table: label column, sub-cells side by side, each line with its date
  and a link to its source. Edit in place; "+" per row. Editing a line supersedes it, and earlier versions
  stay one click away.
- **Migration:** split existing `intake_notes` / `case_notes` by their `## ` headings into facts dated with the
  profile's `updated_at`. Text that matches no heading becomes a "Notes" fact. The old fields stay read-only
  until the migration is confirmed on real data, then they go.
- `arbeitsdiagnose` becomes the active Arbeitsdiagnose fact. Invoices (GebüH diagnosis line) read it from there.
- Kind labels are clinical vocabulary in German (same exemption as the current template, see
  CODEBASE_STANDARDS § Internationalisation). Whether they need English labels for other self-hosters is
  decided in this PR.
- *Why:* gives the case formulation dates, sources and history, and makes the small digests of PR 5 possible.
  This is the change that addresses the root cause.

### PR 5: "Anything for the case sheet?"

- After saving a log, an optional second step: pick a row, write one line, add. "Nothing today" skips it. The
  line becomes a `ClinicalFact` with the session as its source.
- The same action, "send a line to the case sheet", is available on any timeline entry.
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
