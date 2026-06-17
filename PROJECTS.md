# 📋 Projekte - Payments System

**Status**: Production-ready
**Last Updated**: 2026-06-17

## 🔍 Recent Activity

- **2026-06-17 — in-app update banner**: context processor polls GitHub releases API (24h cache); banner shown to authenticated users when a newer release exists; opt-out via `UPDATE_CHECK_DISABLED`.
- **2026-06-17 — npm tooling cleanup**: `npm ci` + lock file in Dockerfile for reproducible CSS builds; `npm audit` added to `./dev.py review`; stale root `requirements-dev.txt` deleted; `dependabot.yml` YAML fix.

> Ältere Einträge: [docs/CHANGELOG.md](docs/CHANGELOG.md)

---

## 📌 Backlog

### Open / Short-term

- **P-010 done (code)**: Crisis fields on `Client` model; org plan in `memory/PERSONAL_TODO.md` — see `docs/guides/EMERGENCY_ACCESS_PLANNING.md`
- **P-011 operational remainder**: Backup timer + secrets rotation — see `memory/PERSONAL_TODO.md`

### Stack / Infrastructure

- **P-044 Alpine.js**: ✅ Complete — see [docs/projects/done/P-044_ALPINE_JS.md](docs/projects/done/P-044_ALPINE_JS.md)
- **P-045 Tailwind CSS**: ✅ Complete — see [docs/projects/done/P-045_TAILWIND_CSS.md](docs/projects/done/P-045_TAILWIND_CSS.md)

### Concept / Mid-term

- **P-029 Import Old Session Logs**: `import_session_logs` management command (`--file`, `--dry-run`, `--create-sessions`); CSV import with Fernet encryption. *Approach: start piecemeal via UI for active clients.*
- **P-023 SMS**: seven.io integration for cancellations + quick SMS; AVV required before API key; ~4h → [docs/projects/todo/P-023_SMS_CANCELLATION.md](docs/projects/todo/P-023_SMS_CANCELLATION.md)
- **OSS follow-ups** (post P-024): extend CI beyond lint (pytest); GitHub Discussions + responsible-disclosure policy → [docs/projects/done/P-024_OSS_RELEASE.md §8](docs/projects/done/P-024_OSS_RELEASE.md)
- **P-039 Django i18n** (post-OSS): Full bilingual UI via `{% trans %}` / `.po` files; ~2 weeks effort → [docs/projects/todo/P-039_I18N.md](docs/projects/todo/P-039_I18N.md)

### ✅ Abgeschlossen

Alle erledigten Projekte: [docs/CHANGELOG.md](docs/CHANGELOG.md) und [docs/projects/done/](docs/projects/done/).

| Projekt | Beschreibung | Abgeschlossen |
| ------- | ------------ | ------------- |
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
| P-010 | Emergency Access Plan (code done: crisis fields on Client model; org plan personal) | März 2026 |
| P-005 | PostgreSQL 17 Upgrade | März 2026 |
| P-004 | Analytics Consolidation | Feb 2026 |
| P-003 | Workflow-Driven Dashboard | Feb 2026 |
| P-002 | Language Consistency | Feb 2026 |
