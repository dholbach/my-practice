# 📋 Projekte - Payments System

**Status**: Production-ready
**Last Updated**: 2026-09-12

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

- **2026-09-10 — v0.5.5 patch release**: dark-on-dark supervision textarea fixed alongside a merge of the two overlapping client-detail Supervision workflows into one (#402); Focus Queue filter counts stuck at 0/1 fixed, a `GROUP BY` column implicitly widened by an inherited `.order_by()` (#403); false-positive unsaved-draft banner on client detail fixed (#404); the `client_detail.html` complexity flagged in the prior entry resolved via a four-phase codebase review — complexity hotspots split, a CSS-token guardrail blind spot fixed (231/460 lines silently unchecked, surfaced a real dark-mode bug), `clinical_views.py`/`email_views.py` test coverage filled in, 11 broken doc links fixed (#408–#411); a stray raw HTML comment on `/bank/review/` fixed (#412); misleading OAuth 7-day-token-expiry guidance corrected (#414); `weasyprint` bumped to close PYSEC-2026-3940 plus routine `pypdf`/`google-auth` bumps (#413/#415, 0 known vulnerabilities). Full list: [docs/CHANGELOG.md](docs/CHANGELOG.md).
- **2026-09-12 — project numbering cleaned up + command palette Phase 1 (P-047)**: audited the `P-XXX` number space and found 63 skipped numbers — P-094 and P-117 had each been named after the GitHub issue they came from (#94, #117) and the sequence carried on from those inflated values. Rule written down in [§ Project Numbering](#-project-numbering) (lowest unused number, never an issue number); the past is deliberately left unrenumbered. Issue #77's "P-040" (a number already taken by Sample Data) renumbered to **P-047** and Phase 1 built: `⌘K`/`Ctrl+K` command palette with 21 jump-to destinations and 8 quick-create actions, rendered server-side as `includes/command_palette.html` so every label stays inside `{% trans %}` and every rule in `tailwind.css` — the header search box and nav are untouched until Phases 2–3. 14 new JS tests; one bug caught by them (a no-match filter left `aria-selected` and the highlight class on a hidden item).

> Ältere Einträge: [docs/CHANGELOG.md](docs/CHANGELOG.md)

---

## 📌 Backlog

### Open / Short-term

- **P-010 Emergency Access Plan**: earlier crisis-field implementation was rolled back (too partial, was blocking other work) — redo needed → [docs/projects/todo/P-010_EMERGENCY_ACCESS_PLAN.md](docs/projects/todo/P-010_EMERGENCY_ACCESS_PLAN.md)
- **P-011 operational remainder**: Backup timer + secrets rotation — see `memory/PERSONAL_TODO.md`
- **P-047 Command Palette (⌘K)**: command-first nav — palette shell + jump/action sections (Phase 1), search folded in (Phase 2), nav stripped to four links (Phase 3); renumbered from the "P-040" in issue #77 → [docs/projects/todo/P-047_COMMAND_PALETTE.md](docs/projects/todo/P-047_COMMAND_PALETTE.md)

### Stack / Infrastructure

- **P-044 Alpine.js**: ✅ Complete — see [docs/projects/done/P-044_ALPINE_JS.md](docs/projects/done/P-044_ALPINE_JS.md)
- **P-045 Tailwind CSS**: ✅ Complete — see [docs/projects/done/P-045_TAILWIND_CSS.md](docs/projects/done/P-045_TAILWIND_CSS.md)

### Concept / Mid-term

- **P-122 General Freelance Practice Type**: Phase 1 (free-form invoice items) done — Phase 2 (standard VAT + advance-payment report) deferred until the Kleinunternehmer election is actually dropped → [docs/projects/todo/P-122_GENERAL_FREELANCE_PRACTICE.md](docs/projects/todo/P-122_GENERAL_FREELANCE_PRACTICE.md)
- **P-029 Import Old Session Logs**: `import_session_logs` management command (`--file`, `--dry-run`, `--create-sessions`); CSV import with Fernet encryption. *Approach: start piecemeal via UI for active clients.*
- **P-023 SMS**: seven.io integration for cancellations + quick SMS; AVV required before API key; ~4h → [docs/projects/todo/P-023_SMS_CANCELLATION.md](docs/projects/todo/P-023_SMS_CANCELLATION.md)
- **OSS follow-ups** (post P-024): ~~extend CI beyond lint (pytest)~~ done 2026-08-21 (#8); GitHub Discussions + responsible-disclosure policy → [docs/projects/done/P-024_OSS_RELEASE.md §8](docs/projects/done/P-024_OSS_RELEASE.md)

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
| P-009 | Client Documentation System: encrypted `ClientProfile`/`SessionLog`/`SupervisionItem`/`ClientNote`, triage summary, supervision queue → [done doc](docs/projects/done/P-009_CLIENT_DOCUMENTATION.md) | Feb 2026 |
| P-005 | PostgreSQL 17 Upgrade | März 2026 |
| P-004 | Analytics Consolidation | Feb 2026 |
| P-003 | Workflow-Driven Dashboard | Feb 2026 |
| P-002 | Language Consistency | Feb 2026 |
