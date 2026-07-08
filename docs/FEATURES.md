# Features Overview

Complete feature list for the Therapy Practice Management System.

## 🏠 Core Features

### Clinical Documentation (Protokoll Tab)
- ✅ Session log entries (SessionLog) — structured per-session notes with interventions, mood tags, session type
- ✅ Freeform dated notes (ClientNote) — encrypted Markdown, user-supplied date
- ✅ Supervision notes — dated Markdown note variant (`note_type=supervision`) interspersed in chronological log; inline ✏️ edit form (date + content, collapsible)
- ✅ `+ Notiz` and `+ Supervision` quick-entry in Protokoll toolbar
- ✅ Supervision tab — agenda items with `besprochen` toggle (separate from Protokoll log)
- ✅ Chronological unified log view (sessions + notes + supervision notes, newest first, collapse >10)
- ✅ Unbilled session delete (blocked if already invoiced)

### Client Detail Cockpit (P-094)
- ✅ Tabbed layout: Überblick / Protokoll / Profil / Abrechnung / Dokumente — replaces sidebar layout
- ✅ Überblick tab: stat cards (diagnosis, last session, session hours, open balance), intake progress widget (4-step bar from existing date fields), recent session one-liners
- ✅ `SessionLog.summary` — unencrypted one-liner field (max 120 chars) shown in Überblick without Fernet decryption; editable in session log form
- ✅ Client tags shown in Überblick tab strip; tag add/remove UI in Profil tab; duplicate tags removed from page header
- ✅ "Details in Profil-Tab" onboarding link switches to the Profil tab and scrolls to the onboarding section

### Client Management
- ✅ Client database with full details
- ✅ Online vs In-person tracking
- ✅ Language preference (DE/EN)
- ✅ Hourly rates (60min, 90min)
- ✅ Active/Inactive status
- ✅ Session history per client
- ✅ Revenue tracking per client
- ✅ Client classification (Probatoric/Active/Established/Dormant)
- ✅ First seen date tracking (Ersttermin)
- ✅ Client detail Zeitraum card shows session-based date range; collapses to single month when all sessions fall in the same month; "seit …" only shown for genuinely active clients
- ✅ Client tagging system — manual tags + auto-managed system tags (`no-next-session`, `incomplete-intake`, `missing-session-log`)
- ✅ System tags automatically stripped from inactive clients on each `update_client_tags` run
- ✅ `no-next-session` tag correctly suppressed when Google-Cal-imported sessions exist but are not yet invoiced
- ✅ "Sammelrechnung" quick-action button on client detail when unbilled sessions exist — links to batch invoice pre-filtered to the relevant month
- ✅ Workflow client list — cards grouped into ⚠️ Needs Attention / ✅ Active / 💤 Inactive based on activity and attention-category tags
- ✅ Live 📝 indicator on client cards for sessions in the last 14 days missing a session log
- ✅ Fillable intake form (Aufnahmebogen) PDF — real form fields pre-filled from client data, remaining fields typable in any PDF viewer
- ✅ Send intake form by email from the onboarding widget — attaches the fillable PDF and marks the step done (`intake_sent_date`)
- ✅ `no-next-session` tag updated immediately by the calendar fetch for affected clients (no wait for the hourly tag run)

### Invoice Management
- ✅ Invoice creation with line items
- ✅ PDF generation (bilingual DE/EN) — redesigned with Newsreader/Hanken Grotesk typography, running footer (IBAN, VAT note, memberships), transparency-correct logo/signature rendering
- ✅ Email sending with custom templates; smart `{sessions_intro}` placeholder — "sessions in May 2026" when all items in same month, "last N sessions" otherwise
- ✅ Status tracking (Draft/Sent/Paid/Cancelled)
- ✅ Duplicate prevention (unique invoice numbers)
- ✅ Payment tracking with paid dates
- ✅ Invoice search and filtering
- ✅ Batch operations
- ✅ Monthly batch invoicing (`/invoices/batch/`) — month picker, one card per client with unbilled sessions, bulk draft creation; free 20-min intro calls excluded automatically
- ✅ Monthly Billing Overview (`/billing/`) — single page showing all clients with activity for a given month: pending calendar events, session count, billed/unbilled split, invoice status, and contextual quick actions; replaces the multi-step clients → client detail → protocol → invoice navigation chain; shows combined `billed/total` count when unbilled sessions exist alongside an invoice; 🚫 badge flags cancelled sessions on invoices; ✏️ edit shortcut appears when cleanup or additions are needed
- ✅ Open Billing Overview (`/billing/open/`) — cross-month view of every unresolved item (warning, draft, sent) grouped by month; identical quick-actions as monthly view; "⚠️ Alle offen" button in monthly nav bar; "Stornierte Sitzung" warning suppressed for paid invoices (not actionable)

### GebüH Billing (P-046)
- ✅ `GebuhZiffer` catalogue — 9 seeded Ziffern (1, 4, 19.1–19.6, 19.8) with Höchstsatz/Mindestsatz, frequency constraints, and Alleinleistung notes
- ✅ `Leistungserfassung` model — per-session GebüH service lines; `betrag` and `vereinbarter_betrag` frozen at entry time
- ✅ `Client.needs_gebueh_invoice` flag — gates all GebüH features per client (PKV/Beihilfe clients only)
- ✅ Quick-entry form (`/gebueh/`) — checkbox list per session, <30 seconds to record; soft warnings for frequency overruns and Alleinleistung conflicts (Ziffer 4)
- ✅ Session row chips — recorded Ziffer numbers shown inline in the Sitzungen tab
- ✅ Invoice PDF — conditional GebüH block: Diagnose line, per-Ziffer rows, Zwischensumme, Restbetrag, Sitzung-gesamt; unchanged layout for non-GebüH clients
- ✅ Probatorik callout — Profil tab hint when diagnosis not yet set; escalates to warning badge after 5+ diagnostic Ziffern recorded

### Session Tracking
- ✅ Historical session data import
- ✅ Monthly session aggregation
- ✅ Duration tracking (15/60/90/120 minutes)
- ✅ Service type classification
- ✅ Cancellation tracking (`Session.cancelled` field — source of truth for capacity analytics)
- ✅ Group session support (`Session.group_size` — therapist-hour normalisation)
- ✅ Session-to-invoice reconciliation
- ✅ Billable toggle (`Session.billable`) — excludes intro calls or non-billable sessions from all billing calculations; toggle button in protocol tab
- ✅ Interactive heatmap visualization
- ✅ Delete unbilled session from client detail (blocked if already invoiced)

---

## 📊 Analytics & Reporting

### Dashboard (P-117)
- ✅ Stats strip — year revenue, year profit, outstanding invoices (count + total, highlights in red), time off with current/upcoming holiday hint
- ✅ Quick-action buttons — "+ Neue Rechnung" / "+ Neue Klient:in" top-right of stats strip
- ✅ Two-pane console — left: Heute (agenda) + Diese Woche (weekly focus); right: Braucht Aktion queue
- ✅ **Braucht Aktion queue** — ranked by urgency; grouped rows: overdue invoices (N · total · client codes · age), drafts ready to send, checklists due; individual rows for each client needing attention (with days-since + last-session date)
- ✅ Capacity monitoring widget — conditional, only shown when a capacity warning is active
- ✅ Status breakdown (Draft/Sent/Paid/Cancelled) — all-time overview
- ✅ Recent invoices overview
- ✅ Dark mode + Privacy mode
- ✅ **Fokus-Aufgaben Widget** — ⭐ toggle on todos, `WeeklyFocusWidgetBuilder` shows focus tasks in dashboard (P-028)

### Analytics Dashboard
- ✅ Time period filters (All/Month/Quarter/Year/Custom)
- ✅ Revenue trends (yearly breakdown)
- ✅ Expense tracking by category
- ✅ Profit analysis (Revenue - Expenses)
- ✅ Revenue vs Expenses vs Withdrawals comparison
- ✅ Top clients by revenue
- ✅ Session type distribution
- ✅ Busiest months analysis
- ✅ Year-over-year comparison
- ✅ Interactive charts with hover tooltips
- ✅ Cancellation rate trend — monthly Ausfallquote (%) over last 24 months (Kapazität tab)
- ✅ Days-to-payment trend — avg days invoice→payment over last 24 months (Umsatz tab)

### Practice Analysis (NEW - Dec 2025)
- ✅ Period-based analysis (Month/Quarter/Half-Year/Year/Custom)
- ✅ Client classification and activity tracking
- ✅ Capacity planning with working days calculation
- ✅ Time-off integration and capacity impact
- ✅ Configurable capacity periods in Practice Settings — multiple periods with different weekly hours; replaces hard-coded 2023-08-01 split
- ✅ Smart insights generation (8 insight types)
- ✅ 4-quarter historical trends
- ✅ Active client ratio tracking
- ✅ Revenue opportunity identification
- ✅ Client concentration warnings
- ✅ Dormant client filtering

### Reports
- ✅ Tax Year Summary (Steuererklärung)
- ✅ Tax Year Summary: Home-Office-Pauschale (calendar-based non-practice weekdays minus holidays/time off), deduction row in Gewinn, improved link contrast
- ✅ Tax quarter overview: all four quarters now sum exactly to the year total — invoices with no `paid_date` fall into their `invoice_date` quarter (same fallback rule as the year summary)
- ✅ Annual tax settlement (Steuerbescheid) tracking on the quarterly tax page
- ✅ Revenue Report with filters
- ✅ Client detail reports
- ✅ Session reconciliation report

### Client Inquiries & Lead Tracking

- ✅ Inquiry pipeline with 9 statuses (Neu → Kontaktiert → Vorgespräch → Warteliste → Aufnahme → Aufgenommen / Abgelehnt / Nicht erreichbar / Kein Match)
- ✅ Source tracking (Empfehlung, Psychotherapie-Informationsdienst, Website, etc.)
- ✅ Contact details (email, phone) per inquiry
- ✅ One-click conversion to Client record
- ✅ Open pipeline as default view — closed inquiries hidden with toggle showing count
- ✅ Milestone dates auto-filled on status transitions (contacted, intro, intake, converted)
- ✅ Analytics panel (einklappbar): conversion funnel, avg wait time per stage (working days, Berlin holidays), source breakdown, monthly trend (last 12 months)
- ✅ Active marketing period display on inquiry list
- ✅ `initial_contact_notes` field — free-text notes for first contact
- ✅ Aufklappbarer Erstgespräch-Leitfaden im Anfragen-Formular (P-037 Ph-2)
  - ✅ Stage-aware Copy-Paste E-Mail-Vorlagen im Anfragen-Formular (P-037 Ph-3) — 8 Statuse, je Betreff + Text mit Kopieren-Button
- ✅ Language field (DE/EN) on inquiries — propagates to Client on conversion; language breakdown in analytics panel; badge in inquiry list
- ✅ Status field at the top of the inquiry form; milestone date auto-fills when status changes
- ✅ Booking URL field on Practice settings; warning shown in inquiry form when not yet configured
- ✅ Client code suggester on inquiry and convert forms — auto-suggests next available code
---

## 💰 Financial Management

### Company Withdrawals
- ✅ Personal withdrawal tracking
- ✅ Date and amount recording
- ✅ Description and notes
- ✅ List view with filtering
- ✅ CRUD operations
- ✅ CSV import support

### Company Expenses
- ✅ Business expense tracking (17 categories)
- ✅ Tax deductible flag
- ✅ Receipt management
- ✅ Category-based organization
- ✅ Date range filtering
- ✅ Year filtering
- ✅ CRUD operations
- ✅ CSV import support

### Time Off Management
- ✅ Vacation/Sick leave/Holiday tracking
- ✅ Date range with duration calculation
- ✅ Year-spanning periods supported
- ✅ Workday calculations (5/7 formula)
- ✅ Capacity impact analysis
- ✅ Period-based calculations
- ✅ Calendar integration

---

## 🔄 Data Import & Integration

### CSV Import
- ✅ Invoice import (multi-format support 2020-2024)
- ✅ Session history import
- ✅ Withdrawal import
- ✅ Expense import
- ✅ Auto-create missing clients
- ✅ German/US decimal parsing
- ✅ Duplicate detection
- ✅ Error reporting with line numbers

### Google Calendar Integration (Phase 1-5 - Complete ✅)

#### Phase 1-2: Foundation
- ✅ OAuth2 authentication with token storage
- ✅ Calendar event import from "Praxis" calendar
- ✅ Automatic client matching via client codes
- ✅ Service type mapping based on duration (15/20/60/90 min)
- ✅ Cancellation detection with "(cancel)" keyword
- ✅ Reinstatement: un-cancelling an event in Google Calendar now restores the Session automatically on next fetch

#### Phase 3-4: Smart Workflow
- ✅ Duplicate detection (checks existing InvoiceItems)
- ✅ Smart auto-selection (ready events pre-selected)
- ✅ Status badges: ✅ Bereit, 🔄 Duplikat, ⚠️ Unbekannt, ❌ Cancelled
- ✅ Free Vorgespräch consultations (0€ rate)
- ✅ First seen date auto-tracking
- ✅ Single draft invoice per client
- ✅ User overrides for client/service selection
- ✅ Bulk import with error reporting

#### Phase 5: Production Polish
- ✅ Automatic token refresh (proactive 5-minute expiry check)
- ✅ API pagination for >250 events (nextPageToken support)
- ✅ Session storage (30-minute cache, reduces API calls)
- ✅ PKCE (S256) in OAuth2 flow — required by Google since 2025
- ✅ Rescheduled events propagate date + time to linked Session (previously only duration was synced)

---

## 🔧 Technical Features

### UI/UX
- ✅ Dark mode with theme toggle
- ✅ Privacy mode (blur sensitive data)
- ✅ Responsive design
- ✅ Interactive charts
- ✅ Toast notifications
- ✅ Modal dialogs
- ✅ Dropdown menus
- ✅ Form validation
- ✅ Loading states
- ✅ E-Mail-Textbausteine (`/tools/boilerplate/`) — 6 copyable DE/EN templates for common practice email scenarios

### Performance
- ✅ N+1 query elimination (73-94% reduction)
- ✅ Database indexing
- ✅ Select/prefetch_related optimizations
- ✅ Aggregation at DB level
- ✅ Query result caching
- ✅ Lazy loading strategies

### Security
- ✅ Environment-based configuration
- ✅ ALLOWED_HOSTS validation
- ✅ CSRF protection
- ✅ Open-redirect guard on all `next=` redirects (`safe_next()` — validates URL starts with `/`)
- ✅ SQL injection prevention (ORM)
- ✅ XSS protection
- ✅ Secure password hashing
- ✅ Admin authentication
- ✅ UniqueConstraints on critical fields
- ✅ Global login enforcement — all views require authentication via `LoginRequiredMiddleware`
- ✅ Practice isolation enforced on all endpoints including `session_toggle` and email views
- ✅ Pre-commit PII guard — staged content checked against a local denylist before every commit
- ✅ Responsible-disclosure policy (`SECURITY.md`)

### Testing
- ✅ 200+ automated tests
- ✅ ~70% code coverage
- ✅ Model tests
- ✅ View tests
- ✅ Utility tests
- ✅ Integration tests
- ✅ Analytics tests
- ✅ Reconciliation tests

### DevOps
- ✅ Docker containerization
- ✅ Docker Compose setup
- ✅ PostgreSQL database
- ✅ Automated backups (systemd timer)
- ✅ Backup/Restore scripts
- ✅ Development scripts
- ✅ Management commands
- ✅ Release smoke test (`./dev.py smoke [vX.Y.Z]`) — boots a released GHCR image with a throwaway DB in an isolated compose project, verifies version + login page, tears down without a trace

---

## 📝 Documentation

### User Documentation
- ✅ README.md with setup instructions
- ✅ EMAIL_IMPLEMENTATION.md
- ✅ BACKUP_SETUP.md
- ✅ SECURITY.md
- ✅ [P-042 Multi-practice tax allocation](../projects/done/P-042_TAX_MULTI_PRACTICE_ALLOCATION.md) — guide + in-app split calculator for splitting daily pauschalen across multiple EÜR

### Developer Documentation
- ✅ CHANGELOG.md (comprehensive)
- ✅ CODE_STRUCTURE.md
- ✅ PERFORMANCE.md
- ✅ IMPORT_VIEWS.md
- ✅ SCRIPTS.md
- ✅ FEATURES.md (this document)

### Code Documentation
- ✅ Docstrings on all functions
- ✅ Inline comments for complex logic
- ✅ Type hints (partial)
- ✅ Example usage in docstrings

---

## 🚀 Recent Additions (Mai 2026)

### OSS Release Prep (6. Mai)

- **AGPL-3.0 license**: `LICENSE` file added; README updated with copyright notice
- **`setup_practice` management command**: interactive wizard prompting for name, address, bank details, and tax status; creates `Practice` + assigns all superusers as owners — no Django admin knowledge required for first-run setup (`./dev.py manage setup_practice`)
- **PII removed from codebase**: hardcoded name + booking URL replaced with `[Ihr Name]` / `[booking URL]` placeholders in inquiry email templates; migration defaults anonymised (0011, 0012, 0027)
- **Seed data: clinical notes**: `seed_sample_data` now creates 2–4 `ClientNote` entries per client using archetype-based `NOTE_TEMPLATES`; skipped gracefully if `FERNET_KEY` is not set
- **Seed data: client code safety**: SG→SAG (Samwise Gamgee), PT→PEK (Peregrin Took) to avoid potential clashes with real client codes

## 🚀 Recent Additions (Juni 2026)

### Seed Data & UI Polish (16. Juni)
- **Seed data: session logs** — `seed_sample_data` creates `SessionLog` entries for ~75% of sessions per client: archetype-specific content, interventions, therapist reflection, mood tags; first session marked as Erstgespräch
- **Seed data: client profiles** — `ClientProfile` created per client with ICD-10 working diagnosis, intake notes, and case formulation; skipped if `FERNET_KEY` not set
- **Seed data: time-off entries** — 8 realistic `TimeOff` records (vacation, training) across 2025–2026 so the Kapazität & Auslastung widget shows real data
- **Seed data: cancelled sessions** — ~8% of sessions seeded as cancelled; populates the Ausfallquote chart
- **Seed data: invoice fixes** — quantities fixed to `1.00` (flat session rate, not hourly multiplication); random 20%-skip removed so invoice numbers are strictly sequential
- **README screenshots** — 5 views added to `docs/screenshots/` (dashboard, invoice detail, analytics, client detail, batch invoicing)
- **Nav emoji alignment** — `nav a` set to `inline-flex; align-items: center` so emoji and text stay on the same line
- **Bank Import badge** — "None Tage" replaced by "Kein Import" when no bank transactions have ever been imported
- **Ausfallquote chart** — fixed: all-zero cancellation rates now render as a flat 0% line instead of "Keine gültigen Daten vorhanden"; `showChartEmptyState` now sizes canvas before drawing text
- **Session log layout** — interventions moved from narrow left column (90px) into right content column, eliminating empty space below short session notes
- **Invoice detail** — tax line `0.00 €` (wrong decimal) replaced with `{{ invoice.tax_amount|currency }}`; salutation warning removed (already present on all email-send forms)

### Tailwind CSS + Dark Mode — P-045 (16. Juni)

- Single CSS source file (`tailwind.css` → `tailwind.out.css`); all 29 per-page CSS files and `common.css` deleted
- `@theme` token system: every colour defined once; `[data-theme="dark"]` overrides flow through automatically — no per-component dark-mode CSS needed
- Zero hardcoded hex colours in non-PDF templates; new semantic classes: `.callout-warning/danger/success/primary`, `.btn-gradient`
- New UI features require zero new CSS files

## 🚀 Recent Additions (April 2026)

### P-040 Sample Data + Bank Import Cleanup (28. April)

- **`seed_sample_data` management command** (`./dev.py manage seed_sample_data`): seeds 45 fictional clients (Tolkien / Le Guin / Greek myth), 900+ sessions with realistic 2-year seasonality, invoices (paid/sent/draft mix), 8 pipeline inquiries, todos, and expenses; `--clear` removes seeded data cleanly; idempotent (no-op if already seeded); `--seed N` for reproducibility; auto-assigns all superusers to the demo practice so it is immediately accessible after login
- **Sample-data isolation**: seeding always uses a dedicated demo practice (slug `demo`); fictional client codes chosen to avoid clashes with real client codes (e.g. Orm Irian uses `OIR`)
- **Getting-started guide**: `docs/guides/GETTING_STARTED.md` — 5-step first-run walkthrough (clone → start → superuser → seed → explore) with a narrated tour of every major feature area

### Bank-Withdrawal-Review + P-028 + P-037 (14. April)

- **Bank-Withdrawal-Review** (`/bank/withdrawals/`): Analog zu `/bank/expenses/` — `auto-withdrawal`-Transaktionen zu `CompanyWithdrawal` gruppieren oder ignorieren; Link vom Bank-Review-Dashboard
- **Fokus-Aufgaben (P-028 Ph-1)**: `is_focus` BooleanField auf `PracticeTodo`; ⭐/☆ HTMX-Toggle in der Todo-Liste; `WeeklyFocusWidgetBuilder` zeigt Sitzungen der Woche + Fokus-Tasks; 2-col "Heute & Diese Woche" Grid im Dashboard
- **Fokus-Aufgaben direkt abhaken (P-028 Ph-2)**: ☐-Knopf im Weekly-Focus-Widget;
  beide Buttons (`☐`, `⭐`) refreshen das gesamte Widget-Fragment via HTMX (`outerHTML`-Swap)
- **Erstgespräch-Guide (P-037 Ph-1/2)**: `initial_contact_notes`-Feld auf `ClientInquiry` + Formular-Integration; aufklappbarer Leitfaden (Zeitplan + Hinweise) im Anfragen-Bearbeitungs-Formular
- **Stage-E-Mail-Vorlagen (P-037 Ph-3)**: Context-sensitive Copy-Paste-Panel im Anfragen-Formular — je nach Status eine passende Vorlage (Betreff + Text, Kopieren-Buttons, 8 Status abgedeckt)

### Feiertags-bereinigte Werktags-Berechnung (13. April)

- Ø Wartezeit in Anfragen-Analytics jetzt in **Werktagen** (Mo–Fr, ohne Berliner Feiertage) statt Kalendertagen
- Kapazitäts- und Ausfall-Berechnungen in Analytics-Dashboard ebenfalls feiertags-bereinigt

### Anfragen-Analytics + Meilenstein-Dates — P-034 (12. April)

- 4 optionale Meilenstein-Datumsfelder auf `ClientInquiry`: `contacted_date`, `intro_date`, `intake_date`, `converted_date`
- Auto-Fill: bei Statuswechsel zu Kontaktiert / Vorgespräch / Aufnahme läuft wird das Datum automatisch auf heute gesetzt (überschreibbar)
- `InquiryConvertView` setzt `converted_date` automatisch beim Aufnehmen
- Auswertungs-Panel auf `/inquiries/` (einklappbar): Pipeline-Funnel mit Anzahl pro Stage, Ø Wartezeit in Tagen pro Transition, Quellen-Breakdown mit Balken, Monats-Trend (letzte 12 Monate)

## 🚀 Recent Additions (März 2026)

### Client Inquiries / Lead Tracking — P-031 (30. März)
- `/inquiries/` list with source + status badges (dark mode aware)
- Create, edit, delete, convert-to-client workflow
- Sources: Google Ads, Google Organic, Website, Referral, Directory, Network, It's Complicated, Other
- Statuses: New → Contacted → Intro Meeting → Waitlist → In Intake → Converted / Declined / Unreachable / Kein Match
- Active Marketing Periods bar showing current campaigns
- Sensitive data (name, email, phone) respects global privacy mode; 🔒 column header icons
- PII scrubbed from 500 error tracebacks (`PIIExceptionReporterFilter`)

### Fahrtkosten / Entfernungspauschale — P-027 (27. März)
- Automatische Berechnung steuerlich absetzbarer Fahrtkosten (§ 9 Abs. 1 Nr. 4 EStG)
- Konfiguration: Pendelentfernung (km) + Praxiswochentage in den Praxiseinstellungen
- `PracticeDayCalculator`: zählt Praxistage (Wochentage − Feiertage Berlin − Urlaub)
- Neuer Abschnitt „🚗 Fahrtkosten" auf `/reports/steuerjahr/` mit Detailaufschlüsselung

### Klientendokument-Upload — P-026 (März)
- `ClientDocument` Modell: Typ (Behandlungsvertrag / Aufnahmebogen / Überweisung / Sonstiges)
- Drag-and-Drop-Upload auf der Klienten-Detailseite (AJAX, kein Seitenreload)
- Dateiname-Inferenz: erkennt Datum, Typ und Beschreibung automatisch
- Speicherpfad: `clients/<code>/<year>/<type>-<date>-<slug>.<ext>`; Löschen via AJAX
- Aufnahmeprozess-Auto-Completion: Upload von Aufnahmebogen / Behandlungsvertrag / Anamnesebogen setzt den jeweiligen Onboarding-Schritt automatisch auf erledigt

### InvoiceItem-Normalisierung — P-025 (März)
- Sitzungsfelder (`session_date`, `duration`, `session_type`) in separates `Session`-Modell ausgelagert
- `InvoiceItem.session` FK → `Session`; Felder werden beim Speichern automatisch in `Session` geschrieben
- Saubere Trennung: Rechnungsposten vs. klinische Sitzungsdaten; Kalender-Import aktualisiert

---

## ❌ Not Planned

Features explicitly out of scope:
- Complex accounting (use dedicated software)
- Multi-practice support
- Insurance billing (German system)
- Video conferencing
- Payment processing (online payments)
- Multi-language UI (German only, until P-039)

For planned and in-progress work see [PROJECTS.md](../PROJECTS.md) and [docs/projects/](projects/).

---

## 🐳 Self-hosting

- ✅ Pre-built multi-arch Docker image (`amd64` + `arm64`) published to GHCR
- ✅ `prod.py` — one-command setup: generates secrets, pulls image, starts stack, walks through login + practice creation
- ✅ `docker-compose.prod.yml` — production compose file; downloaded automatically by `prod.py setup`
- ✅ Version-pinned: `prod.py` and `docker-compose.prod.yml` always match; `update` notifies when a newer `prod.py` is available
- ✅ In-app update banner — checks GitHub releases once per day; shows a dismissible banner when a newer release is available; opt-out via `UPDATE_CHECK_DISABLED=true`

Last Updated: 17. Juni 2026
