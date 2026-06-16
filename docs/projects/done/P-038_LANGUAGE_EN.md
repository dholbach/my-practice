# P-038: Language Consistency — Code/Docs/Slugs to English

**Status**: DONE
**Completed**: 2026-04-17
**Priority**: Low (do incrementally — migrate files as you touch them)
**Depends on**: nothing
**Blocks**: P-024 (OSS Release)

## Decision

Code, comments, docstrings, filenames, URL slugs, and documentation are English.
UI/app-facing text (labels, buttons, messages) stays German until P-039 (Django i18n).
See CLAUDE.md Language Policy table for the full rule set.

---

## Completed

### Phase 1 — Mechanical renames ✅

- 4 German URL slugs → English (`contract-pdf`, `send-contract`, `intake-form-pdf`, `send-questionnaire`)
- 2 German template filenames → English (`treatment_contract_pdf.html`, `intake_form_pdf.html`)
- 1 orphaned template deleted (`anamnesebogen_pdf.html` — no references)
- 1 management command renamed: `import_behandlung_odt.py` → `import_session_odt.py`

### Phase 2 — Python comments, docstrings, developer-facing output ✅

Comprehensive grep sweep (`[äöüÄÖÜß]` in comments/docstrings) + targeted fixes:

- `config/exception_reporter.py` — class/method docstrings + inline comments
- `config/settings.py` — one-line comment
- `management/commands/check_media.py` — help text + all stdout messages
- `management/commands/clearbanktransactions.py` — error/stdout messages
- `management/commands/fetch_calendar_events.py` — help text + all stdout/logger messages
- `models/client.py` — `"dokument"` fallback → `"document"`
- `models/financial.py` — `"beleg"` fallback → `"receipt"` (×2)
- `utils/calendar_import_helpers.py` — two inline comments + one error string
- `utils/google_calendar.py` — one inline comment
- `views/operational_views.py` — one inline comment
- `tests/test_calendar_import_helpers.py` — test assertion updated to match new EN string
- `tests/test_google_calendar.py`, `tests/test_views_tax.py` — docstrings

**Exclusions (P-039 scope):** `verbose_name`, `help_text`, form labels, UI strings, and clinical
template content (`INTAKE_NOTES_TEMPLATE`) remain German until Django i18n is complete.

### Phase 3 — Project/operations docs translation ✅

Pre-OSS-release sweep of all remaining German docs:

- `docs/guides/BACKUP_SETUP.md` — translated
- `docs/guides/CLIENT_TAGGING.md` — translated
- `docs/guides/EMAIL_IMPLEMENTATION.md` — translated
- `docs/operations/SECURITY.md` — translated
- `docs/operations/REINSTALL_CHECKLIST.md` — translated
- `docs/operations/SCRIPTS.md` — translated
- `docs/operations/DPIA.md` — translated
- `docs/projects/todo/P-023_SMS_CANCELLATION.md` — translated
- `docs/projects/wip/P-024_OSS_RELEASE.md` — translated
- `docs/projects/todo/P-039_I18N.md` — translated
- `docs/projects/wip/P-009_CLIENT_DOCUMENTATION.md` — 2 inline German terms fixed
- `docs/architecture/CODE_STRUCTURE.md` — full 935-line German → English translation

Committed: `33b0361`

---

## Related

- [CLAUDE.md Language Policy](../../../CLAUDE.md#language-policy-p-038)
- [P-024 OSS Release](P-024_OSS_RELEASE.md)
- [P-039 Django i18n](../todo/P-039_I18N.md)
