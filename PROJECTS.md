# 📋 Projekte - Payments System

**Status**: Production-ready
**Last Updated**: 2026-10-14

## 🔢 Project Numbering

**Next number = the lowest unused `P-XXX`, and never a GitHub issue/PR number.**

Project numbers are pure identifiers — they carry no chronological meaning (the
"Abgeschlossen" table below is date-ordered and runs P-050, P-039, P-121, P-046 …
all in the same month), so reusing a gap costs nothing.

Gaps exist because P-094 and P-117 were each named after the GitHub issue they came
from (#94 "client detail — Überblick tab", #117 "dashboard redesign — two-pane
console"), and the sequence then carried on from those inflated values
(P-095–P-100, P-118–P-122). That skipped 63 numbers. **Don't renumber the past** to
close the gaps — those numbers are cross-referenced from `docs/FEATURES.md`,
`docs/CHANGELOG.md`, `docs/architecture/CODE_STRUCTURE.md` and code comments. Fill
from the bottom instead.

Currently unused: 6, 8, 48, 49, 51–93, 96, 98, 101–116. To re-check before claiming
one:

```bash
grep -rho "P-[0-9]\{3\}" --include=*.md --include=*.py --include=*.html \
    --include=*.js --include=*.css . | sort -u
```

---

## 🔍 Recent Activity

- **2026-10-21 — Inquiry charts, lapse + anonymise**: `/inquiries` gets a monthly chart with marketing periods drawn as lanes (generic `lanes` option on `MPChart.bar`) and an open-inquiry ageing list (PR #533). Follow-up adds a *Lapsed* status and `manage.py tidy_inquiries` (lapse after 60 days without a step, anonymise closed non-client inquiries 180 days after last contact); not on the scheduled-jobs timer yet — the retention period is still to be confirmed with the Verband.
- **2026-10-15 — Screenshot refresh (#148)**: README screenshots retaken on `seed_sample_data` in the English UI, mixing light and dark theme — dashboard, Focus Queue, GebüH invoice breakdown, client heatmap, inquiries, both diagnosis callouts (standard + escalated), batch invoicing; the analytics shot is the Capacity tab. `seed_sample_data` now seeds capacity periods and keeps its cancellations (billing them as therapy had cleared the flag), so that tab is populated; its utilisation subtitle lists the practice's own targets instead of a hardcoded history. Inquiry row actions fixed (compact `.btn`s; `.btn.btn-success` scoped like `.btn-danger`).

> Ältere Einträge: [docs/CHANGELOG.md](docs/CHANGELOG.md)

---

## 📌 Backlog

### Open / Short-term

- **P-010 Emergency Access Plan**: earlier crisis-field implementation was rolled back (too partial, was blocking other work) — redo needed → [docs/projects/todo/P-010_EMERGENCY_ACCESS_PLAN.md](docs/projects/todo/P-010_EMERGENCY_ACCESS_PLAN.md)
- **P-011 operational remainder**: install the backup timer on the production host (`sudo bash scripts/install-system-jobs.sh`, #508) and rotate secrets (`FERNET_KEY` via `manage.py encryption rotate`, #500) — the tooling exists now; see `memory/PERSONAL_TODO.md`

### Concept / Mid-term

- **P-122 General Freelance Practice Type**: Phase 1 (free-form invoice items) done — Phase 2 (standard VAT + advance-payment report) deferred until the Kleinunternehmer election is actually dropped → [docs/projects/todo/P-122_GENERAL_FREELANCE_PRACTICE.md](docs/projects/todo/P-122_GENERAL_FREELANCE_PRACTICE.md)
- **P-029 Import Old Session Logs**: `import_session_logs` management command (`--file`, `--dry-run`, `--create-sessions`); CSV import with Fernet encryption. *Approach: start piecemeal via UI for active clients.*
- **P-023 SMS**: seven.io integration for cancellations + quick SMS; AVV required before API key; ~4h → [docs/projects/todo/P-023_SMS_CANCELLATION.md](docs/projects/todo/P-023_SMS_CANCELLATION.md)
- **OSS follow-ups** (post P-024): ~~extend CI beyond lint (pytest)~~ done 2026-08-21 (#8); GitHub Discussions + responsible-disclosure policy

### ✅ Abgeschlossen

Alle erledigten Projekte: [docs/CHANGELOG.md](docs/CHANGELOG.md) und [docs/projects/done/](docs/projects/done/).

| Projekt | Beschreibung | Abgeschlossen |
| ------- | ------------ | ------------- |
| P-047 | Command Palette (⌘K): server-rendered palette with search + 21 jump-to destinations + 8 quick-create actions; nav stripped to four links, `global-search.js` retired | Sep 2026 |
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
| P-016 | Stack Modernisation (M-01–M-14; M-04/M-11Ph2/M-12 Won't Do) | Apr 2026 |
| P-015 | Steuer-PDF-Sammeldownload | Feb 2026 |
| P-014 | Zahlungserinnerung per E-Mail | Feb 2026 |
| P-013 | Workflow Dashboard (Phasen 1–3) | Feb 2026 |
| P-012 | Operational Checklist + Pause | Feb 2026 |
| P-011 | Security Foundation (LUKS + Yubikey + DPIA) | Feb 2026 |
| P-009 | Client Documentation System: encrypted `ClientProfile`/`SessionLog`/`SupervisionItem`/`ClientNote`, triage summary, supervision queue | Feb 2026 |
| P-005 | PostgreSQL 17 Upgrade | März 2026 |
| P-004 | Analytics Consolidation | Feb 2026 |
| P-003 | Workflow-Driven Dashboard | Feb 2026 |
| P-002 | Language Consistency | Feb 2026 |
