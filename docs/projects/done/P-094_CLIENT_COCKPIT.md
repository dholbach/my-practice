# P-094 Client Detail Cockpit

**Status**: DONE (merged 2026-06-24, PR #95)

## Goal

Redesign the client detail page as a tabbed "prep cockpit" — a single-glance view before sessions showing clinical status, billing state, and intake progress.

## What was built

### Layout
- Five top-level tabs replacing the old sidebar layout: **Überblick / Protokoll / Profil / Abrechnung / Dokumente**
- Tab state preserved in URL hash (`#ptab-<name>`)

### Überblick tab
- Stat cards: working diagnosis, last session (timesince), session hours + count, open balance (warning style when non-zero)
- Intake progress widget: 4-step bar (Aufnahme → Vertrag → Anamnese → Abschluss) derived from existing `Client` date fields — no new model needed
- Therapy type badge: rendered from existing client tags in the page header
- Recent session one-liners: last 5 `SessionLog` entries showing date, mood tags, and `summary`

### New model field
- `SessionLog.summary`: `CharField(max_length=120, blank=True)` — unencrypted, so it renders in Überblick without the Fernet key
- Migration: `0003_sessionlog_summary`
- Session log create/edit views updated to save/load the field
- Session log form: new one-liner input added after session type

### i18n
- `client_detail.html` and `session_log_form.html` fully wrapped per P-039 convention
- All fuzzy gettext auto-suggestions reviewed and corrected manually

## Key decisions

- `SessionLog.content` is Fernet-encrypted → cannot show in overview; `summary` is intentionally unencrypted (same rationale as `mood_tags`)
- Intake steps derived from 4 existing `Client` date fields — no new model
- Old partials (`client_detail_tabs.html`, `client_detail_sidebar.html`) kept on disk but no longer included — delete in a future cleanup PR
