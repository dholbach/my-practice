# P-120: Multi-instrument questionnaire wiring + page-break fix

Follow-up to [P-118](P-118_QUESTIONNAIRE_PDFS.md)/[P-119](P-119_QUESTIONNAIRE_CHECKLIST_FREETEXT.md).
P-118 deliberately hardcoded the send/email flow to GAD-7, deferring
generalization "until there's a second instrument to prove the pattern
against." Building an ADNM-20 content file (instance-local, never
committed — see the [local git repo note](#local-content-history) below)
was that second instrument, and exposed three real issues.

## What changed

**Page-break bug in long grids.** GAD-7's 7-row grid never spans a page,
so WeasyPrint splitting a `<tr>` across a page boundary — and silently
dropping that row's radio buttons — never showed up until ADNM-20's
20-row grid hit it (2 of 20 rows lost their inputs). Fixed with
`break-inside: avoid` / `page-break-inside: avoid` on `.q-grid tbody tr`,
the same pattern already used for invoice line tables.

**Missing Docker volume mount.** `MY_PRACTICE_DATA_DIR/questionnaires/` was
never bind-mounted into the container (unlike `documents/`), so
instance-local content would have silently 404'd in Docker even though it
worked via `./dev.py run`. Added the mount to `docker-compose.yml` and
`docker-compose.prod.yml`.

**Hardcoded single-instrument wiring generalized:**
- `SendQuestionnairePdfEmailView` now takes `code` from the URL
  (`clients/<pk>/send-questionnaire-pdf/<code>/`) instead of being
  hardcoded to `gad7`. `BaseClientEmailView.get`/`post` widened to accept
  arbitrary extra URL kwargs.
- Filename display label (e.g. `"GAD-7"`) moved from a hardcoded dict in
  `email_views.py` into the content file itself
  (`QuestionnaireContent.filename_label`, optional, falls back to the
  uppercased code) — so committed code never needs to name a specific
  licensed instrument.
- New `list_available_questionnaires()` scans both the shipped
  `questionnaire_content/` dir and instance-local
  `MY_PRACTICE_DATA_DIR/questionnaires/` for content files. The client detail
  "Assessments" card now loops over whatever's actually available instead
  of hardcoding "Send GAD-7" / "Send ADNM-20" buttons — important because
  this is a public repo other people can deploy: a hardcoded ADNM-20
  button would show up (and 404) for every install, even ones without that
  license.

**Stale settings name fixed in passing.** P-032 renamed the `MY_PRACTICE_DATA_DIR`
env var (was `PAYMENTS_DATA_DIR`), but the internal Django settings
constant was left as `PAYMENTS_DATA_DIR`, and `docs/operations/SCRIPTS.md`/
`SECURITY.md` still referenced the old env var name — a docs bug (following
those instructions today would reference a shell variable that no longer
exists). Renamed the constant to match and fixed the stale doc references.

## Local content history

`MY_PRACTICE_DATA_DIR/questionnaires/` (host: `../my-practice-data/questionnaires/`)
is now its own local-only git repo — no remote, never pushed anywhere —
purely for edit history on the licensed content files themselves.
Durability is already covered by `./scripts/backup.sh`; this is just diff/
rollback for typo fixes and wording tweaks.
