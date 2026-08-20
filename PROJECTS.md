# 📋 Projekte - Payments System

**Status**: Production-ready
**Last Updated**: 2026-08-19

## 🔍 Recent Activity

- **2026-08-19 — Dark-mode contrast + CSS token guardrail (post-v0.5.0)**: five components had effectively invisible text in dark mode (contrast ≈1.0) — the client triage card, the completed onboarding step, the expense receipt dropzone, and the login page's wrong-password alert. Same cause each time: a hardcoded light background that doesn't flip with the theme, while the text colour comes from a `--color-*` token that does. Found by rendering every literal-hex rule in headless Chromium under both themes and computing real WCAG contrast rather than reading CSS. Also fixed two declarations that were being dropped entirely (`var(--color-surface-alt)` referenced but never defined, so the GebüH chip background and row hover silently did nothing), four hardcoded German strings in `bank_review.js` (the i18n guardrail never scans JS), and ~15 dead CSS classes including the never-implemented `.timeline*` block and the rolled-back P-010's `.crisis-badge`/`.emergency-*`. New `tests/test_css_tokens.py` ratchets both failure modes; it caught `.billing-status--sent` on its first run. Root cause addressed too: `CODEBASE_STANDARDS.md`'s dark-mode examples taught token names that don't exist (`--card-bg`, `--text-primary`, `--link-color`), which is plausibly where the invented ones came from — corrected, and renumbered to M-PAT-07 since M-PAT-06 is the form draft guard (#366).
- **2026-08-19 — Client detail cockpit consolidation (post-v0.5.0)**: the Überblick and Profil tabs merged into one Overview tab (5 → 4), dropping a read-only tag strip and case-notes preview that duplicated content already visible further down the same tab; tab buttons now show a dot indicator when a draft-guarded form inside them has unsaved edits (the native `beforeunload` dialog can't say *which* tab the edit is in), via a new bubbling `draftguard:dirty` event on `form_draft_guard.js`; practice logo and header padding shrunk, saving ~40px of chrome above the fold on every page (#362). Follow-up docs pass: `FEATURES.md`'s cockpit section still described the old 5-tab layout, the deleted tag strip, and a "Details in Profil-Tab" link that no longer switches tabs; M-PAT-06 in CLAUDE.md now documents the `draftguard:dirty` event so the tab-indicator pattern is reusable.

> Ältere Einträge: [docs/CHANGELOG.md](docs/CHANGELOG.md)

---

## 📌 Backlog

### Open / Short-term

- **P-010 Emergency Access Plan**: earlier crisis-field implementation was rolled back (too partial, was blocking other work) — redo needed → [docs/projects/todo/P-010_EMERGENCY_ACCESS_PLAN.md](docs/projects/todo/P-010_EMERGENCY_ACCESS_PLAN.md)
- **P-011 operational remainder**: Backup timer + secrets rotation — see `memory/PERSONAL_TODO.md`

### Stack / Infrastructure

- **P-044 Alpine.js**: ✅ Complete — see [docs/projects/done/P-044_ALPINE_JS.md](docs/projects/done/P-044_ALPINE_JS.md)
- **P-045 Tailwind CSS**: ✅ Complete — see [docs/projects/done/P-045_TAILWIND_CSS.md](docs/projects/done/P-045_TAILWIND_CSS.md)

### Concept / Mid-term

- **P-122 General Freelance Practice Type**: Phase 1 (free-form invoice items) done — Phase 2 (standard VAT + advance-payment report) deferred until the Kleinunternehmer election is actually dropped → [docs/projects/todo/P-122_GENERAL_FREELANCE_PRACTICE.md](docs/projects/todo/P-122_GENERAL_FREELANCE_PRACTICE.md)
- **P-029 Import Old Session Logs**: `import_session_logs` management command (`--file`, `--dry-run`, `--create-sessions`); CSV import with Fernet encryption. *Approach: start piecemeal via UI for active clients.*
- **P-023 SMS**: seven.io integration for cancellations + quick SMS; AVV required before API key; ~4h → [docs/projects/todo/P-023_SMS_CANCELLATION.md](docs/projects/todo/P-023_SMS_CANCELLATION.md)
- **OSS follow-ups** (post P-024): extend CI beyond lint (pytest); GitHub Discussions + responsible-disclosure policy → [docs/projects/done/P-024_OSS_RELEASE.md §8](docs/projects/done/P-024_OSS_RELEASE.md)

### ✅ Abgeschlossen

Alle erledigten Projekte: [docs/CHANGELOG.md](docs/CHANGELOG.md) und [docs/projects/done/](docs/projects/done/).

| Projekt | Beschreibung | Abgeschlossen |
| ------- | ------------ | ------------- |
| P-050 | Focus Queue: unified `Task` model (extends `PracticeTodo` with `task_type`, `snoozed_until`, generic `related_object`), `sync_focus_queue_tasks` materializes derived signals (missing session log, unpaid/unsent invoices, checklists) as real rows; new `/focus/` page replaces `/todos/` and the dashboard's "Braucht Aktion" pane | Jul 2026 |
| P-039 | Django i18n: dedicated 6-phase sweep — every template, Python view/form/util, model, `admin.py`, JS-string surface wrapped (English msgids, German `.po` translations); guardrail test as a ratchet | Jul 2026 |
| P-121 | Time-off CRUD (`/timeoff/`, previously admin-only) + multi-period client heads-up email with date-only bilingual content and a scannable recipient table | Jul 2026 |
| P-046 | GebüH-Abrechnung: Ziffern catalogue + `Leistungserfassung` per session, GebüH-compliant invoice PDF (headline + collapsed detail lines), Restbetrag decomposition, invoice-detail tightening | Jul 2026 |
| P-120 | Questionnaire multi-instrument wiring: page-break fix for long grids, Docker volume mount for instance-local content, dynamic "Assessments" card (no hardcoded instrument names in committed code) | Jul 2026 |
| P-119 | Questionnaire PDFs: checklist + freetext block types, dual-scale grids (`column_groups`), per-section field-name prefixing to avoid collisions, unrecognized section types now raise instead of silently dropping | Jul 2026 |
| P-118 | Clinical Questionnaire PDFs (pilot): GAD-7 branded fillable PDF, content/template separation for future licensed instruments, send flow via new "Assessments" card | Jul 2026 |
| P-117 | Dashboard Redesign: stats strip, two-pane console (Heute / Braucht Aktion), ActionQueueBuilder with grouped rows, charts → Analytics, heatmap → Analytics Clients tab | Jul 2026 |
| P-024 | OSS Release: repo public (AGPL-3.0, `v0.1.0`), orphan push without private history, topics/description set; post-release onramp (CONTRIBUTING, CoC, issue/PR templates, lint CI, compliance prominence) | Jun 2026 |
| P-045 | Tailwind CSS: full migration — 29 per-page CSS files deleted, `common.css` merged, `@theme` token system, zero hardcoded hex in templates, dark mode everywhere | Jun 2026 |
| P-044 | Alpine.js: CDN drop-in, `inline-handlers.js` + `email_card.js` deleted, all inline event handlers migrated across 16 templates | Jun 2026 |
| P-100 | Complexity reduction: all 7 radon hotspots → extracted builders, processors, topic methods | Mai 2026 |
| P-043 | Bank Statement Import (CSV): GLS CSV parser, transaction matching, auto-reconciliation with invoices | Feb 2026 |
| P-042 | Multi-practice Pauschale split calculator + TaxYearNote + WorkdayAuditCalculator | Apr 2026 |
| P-032 | Project rename `payments_app` → `my_practice` (Ph-A–D+F done; Ph-E deferred into P-024) | Apr 2026 |
| P-040 | Sample Data (`seed_sample_data`): 45 Tolkien/Le Guin/Greek chars, 2-yr seasonality, invoices, inquiries | Apr 2026 |
| P-041 | Monatsabrechnung (`/invoices/batch/`): month picker, client cards, bulk draft creation; auto-skip free sessions | Apr 2026 |
| P-038 | Language EN cleanup (URL slugs, Python comments, all docs) | Apr 2026 |
| P-037 | Geführter Anfragen-Workflow (Ph-1–3: Notizfeld, Erstgespräch-Guide, Stage-E-Mail-Vorlagen) | Apr 2026 |
| P-028 | Dashboard WeeklyFocus Widget (is_focus-Toggle, ☐-Complete-Button im Widget) | Apr 2026 |
| P-034 | Anfragen-Analytics + Milestone-Dates (`contacted_date`, `intro_date`, `intake_date`, `converted_date`); Funnel + Ø Wartezeit + Quellen-Panel auf `/inquiries/` | Apr 2026 |
| P-036 | Calendar→Session decoupled flow (Phasen 1–3: auto-Session, 1-click billing, import filter) | Apr 2026 |
| P-035 | Session-Centric Calculations (Session.cancelled + group_size; alle Analytics/Capacity auf Session-Queries umgestellt) | Apr 2026 |
| P-033 | E-Mail-Textbausteine (`/tools/boilerplate/`, 6 DE/EN-Karten, Copy-Button) | Apr 2026 |
| P-030 | Session List Collapse auf Klientendetail (erste 10 sichtbar, Rest toggle) | Apr 2026 |
| P-031 | Client Inquiries / Lead Tracking | März 2026 |
| P-027 | Fahrtkosten / Entfernungspauschale | März 2026 |
| P-026 | Klientendokument-Upload | März 2026 |
| P-025 | InvoiceItem-Normalisierung | März 2026 |
| P-022 | Media + Backups außerhalb Repo | März 2026 |
| P-021 | Git-History-Bereinigung | März 2026 |
| P-020 | Belegverwaltung | März 2026 |
| P-019 | Zweisprachige PDFs | März 2026 |
| P-018 | Aufnahmeprozess-Workflow | März 2026 |
| P-017 | Behandlungsvertrag PDF | März 2026 |
| P-016 | Stack Modernisation (M-01–M-14; M-04/M-11Ph2/M-12 Won't Do) → [done doc](docs/projects/done/P-016_MODERNISATION.md) | Apr 2026 |
| P-015 | Steuer-PDF-Sammeldownload | Feb 2026 |
| P-014 | Zahlungserinnerung per E-Mail | Feb 2026 |
| P-013 | Workflow Dashboard (Phasen 1–3) | Feb 2026 |
| P-012 | Operational Checklist + Pause | Feb 2026 |
| P-011 | Security Foundation (LUKS + Yubikey + DPIA) | Feb 2026 |
| P-005 | PostgreSQL 17 Upgrade | März 2026 |
| P-004 | Analytics Consolidation | Feb 2026 |
| P-003 | Workflow-Driven Dashboard | Feb 2026 |
| P-002 | Language Consistency | Feb 2026 |
