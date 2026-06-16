# P-029: Import Old Session Logs (ODT)

## Goal

Import session notes and clinical data from historical `Behandlung.odt` files into the
Django system — non-destructive, no duplicates.

## Approach: ODT parser + management command

### Two-step workflow

```bash
# 1. Inspect file (no writes)
python app/odt_to_json.py Behandlung.odt --pretty

# 2. Dry run (preview what would be imported)
./dev.py manage import_session_odt --odt-file Behandlung.odt --client-code AB --dry-run

# 3. Actual import
./dev.py manage import_session_odt --odt-file Behandlung.odt --client-code AB --duration 60
```

### What gets imported

| ODT section | Target | Behaviour |
| ----------- | ------ | --------- |
| Anamnesis table | `ClientProfile.intake_notes` (Markdown) | Only if empty |
| Topics / family dynamics / I-You / challenges / future work | `ClientProfile.case_notes` (Markdown) | Only if empty |
| Supervision questions (list) | `ClientNote` (note_type=supervision), one per item, date=today | Always created |
| Session table (date, observations, …) | `Session` + `SessionLog` per row | `get_or_create` — skips if log already exists |

### Session field mapping

| ODT field | Django field |
| --------- | ------------ |
| `datum` | `Session.session_date` (DD.MM.YYYY, DD.MM.YY, YYYY-MM-DD) |
| `bezeichnung` | `SessionLog.session_type` (keyword mapping) |
| `wahrnehmung` + `sitzung` + `was_half` + `freitext` | `SessionLog.content` |
| `gefuehl_danach` + `wie_ging_es_mir` | `SessionLog.therapist_reflection` |

### Session type mapping (from Bezeichnung)

- erst / vorgespräch / intake → `erstgespraech`
- krise / notfall → `krisenintervention`
- abschluss / ende / letzte → `abschlussphase`
- ausfall / absage / cancel → `ausfall`
- (else) → `standard`

## Relevant files

- `app/my_practice/models/clinical.py` — `Session`, `SessionLog`, `ClientProfile`

## Status

**Paused.** `app/odt_to_json.py` and `management/commands/import_session_odt.py` were
removed in June 2026 — the command was incomplete, format-specific, and not appropriate
for the OSS release. If this is picked up again, start fresh from the design above rather
than trying to recover the deleted files from git history.
