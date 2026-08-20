# Features Overview

**New here?** This is a self-hosted practice-management app for independent, private-pay
practices (therapy, coaching, and similar) — client records, session tracking, invoicing,
analytics, and a few clinical-documentation tools, built to keep client data on hardware
you control instead of a third-party SaaS. It's a Django app you run yourself; see
[GETTING_STARTED.md](guides/GETTING_STARTED.md) for the fastest way to click through a
populated demo, or the [README](../README.md) for the "why" and a five-minute overview.

This document is the exhaustive reference — every feature that's shipped, grouped by area.
If you just want the highlights, the README's "What it does" section is shorter and a
better starting point. Jump to a section:

- [Core Features](#core-features) — clinical documentation, client management, invoicing, GebüH billing, sessions
- [Analytics & Reporting](#analytics--reporting) — dashboard, analytics tabs, tax reports, inquiry pipeline
- [Financial Management](#financial-management) — withdrawals, expenses, time off
- [Data Import & Integration](#data-import--integration) — CSV import, Google Calendar
- [Technical Features](#technical-features) — UI/UX, performance, security, testing, DevOps
- [Self-hosting](#self-hosting) — Docker image, update checks

For what's changed recently, see [CHANGELOG.md](CHANGELOG.md) — that's the dated,
chronological record; this document only tracks current state.

---

## 🏠 Core Features

### Clinical Documentation (Protokoll Tab)
- ✅ Session log entries (SessionLog) — structured per-session notes with interventions, mood tags, session type
- ✅ Freeform dated notes (ClientNote) — encrypted Markdown, user-supplied date
- ✅ Supervision notes — dated Markdown note variant (`note_type=supervision`) interspersed in chronological log; inline ✏️ edit form (date + content, collapsible)
- ✅ `+ Notiz` and `+ Supervision` quick-entry in Protokoll toolbar
- ✅ Supervision tab — agenda items with `besprochen` toggle (separate from Protokoll log)
- ✅ Chronological unified log view (sessions + notes + supervision notes, newest first, collapse >10)
- ✅ Unbilled session delete (blocked if already invoiced)
- ✅ GebüH-recorded indicator on session rows — the GebüH button shows a visual marker once a code has been entered for that session

### Client Detail Cockpit (P-094)
- ✅ Tabbed layout: Overview / Protokoll / Abrechnung / Dokumente — replaces sidebar layout
- ✅ Overview tab: stat cards (diagnosis, last session, session hours, open balance), intake progress widget (4-step bar from existing date fields), recent session one-liners, and the client's profile/tag/onboarding detail further down the same tab — originally two separate tabs (Überblick + Profil), merged once the split proved to be mostly duplicated content
- ✅ `SessionLog.summary` — unencrypted one-liner field (max 120 chars) shown in the Overview tab without Fernet decryption; editable in session log form
- ✅ Tag add/remove UI in the Overview tab; duplicate tags removed from page header
- ✅ "Details ↓" onboarding link scrolls to the onboarding section further down the Overview tab
- ✅ Tab buttons show a dot indicator + "Unsaved changes" tooltip when a draft-guarded form inside them has unsaved edits — the browser's own beforeunload dialog can't say which tab the edit is in

### Focus Queue (P-050)
- ✅ Unified task list (`/focus/`) — replaces the old `/todos/` list and the dashboard's "Needs Action" pane; manual tasks and materialized system signals (missing session log, unpaid/unsent invoice, pending checklist, open supervision topic) live side by side as real, closeable rows
- ✅ `sync_focus_queue_tasks` management command materializes and auto-closes derived tasks; runs on its own daily systemd timer
- ✅ Type filter — colour-coded pill buttons matching each task type's badge colour
- ✅ Reference date per row — invoice date, session date, or task creation date, whichever is most relevant
- ✅ Real undo — the complete checkbox toggles complete/incomplete instead of only marking done; the just-completed row stays visible in place, struck through
- ✅ "📅 Today" quick action — sets a task's due date to today in one click; due-today-or-overdue tasks always sort ahead of the rest of the queue
- ✅ "+ Task" button on the client detail page creates a task pre-linked to that client
- ✅ Dashboard's "This Week" widget shares the same `due_date` signal, so due-today/overdue tasks show up in both places

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
- ✅ Client tagging system — manual tags + auto-managed system tags (`no-next-session`, `incomplete-intake`)
- ✅ System tags automatically stripped from inactive clients on each `update_client_tags` run
- ✅ `no-next-session` tag correctly suppressed when Google-Cal-imported sessions exist but are not yet invoiced
- ✅ "Sammelrechnung" quick-action button on client detail when unbilled sessions exist — links to batch invoice pre-filtered to the relevant month
- ✅ Workflow client list — cards grouped into ⚠️ Needs Attention / ✅ Active / 💤 Inactive based on activity and attention-category tags
- ✅ Live 📝 indicator on client cards for sessions in the last 14 days missing a session log
- ✅ Fillable intake form (Aufnahmebogen) PDF — real form fields pre-filled from client data, remaining fields typable in any PDF viewer
- ✅ Send intake form by email from the onboarding widget — attaches the fillable PDF and marks the step done (`intake_sent_date`)
- ✅ `no-next-session` tag updated immediately by the calendar fetch for affected clients (no wait for the hourly tag run)
- ✅ Clinical questionnaire PDFs (P-118 pilot) — GAD-7 rendered as a fillable, branded PDF (DE/EN) and sent by email from the client detail page; question content is separated from the template so licensed instruments (e.g. BDI-II, ADNM-20) can be added later without their text entering the repo
- ✅ Questionnaire PDFs support `checklist` and `freetext` block types, and grids with multiple independent response scales per statement (`column_groups`) (P-119) — enables multi-part instruments like ADNM-20 once their content file is sourced
- ✅ Client detail "Assessments" card lists whatever questionnaire instruments actually have content available, sending/download links generated dynamically (P-120) — no send flow is hardcoded to a single instrument anymore
- ✅ Shut-D (Shutdown Dissociation Scale) shipped in-repo as a second public instrument (Schalinski et al. 2016, CC BY-SA 4.0)

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
- ✅ Free-form invoice items (P-122 Phase 1) — invoice line items can skip the linked session entirely and use a free-text description instead, for day-rate/project billing (e.g. IT consulting); opt-in per practice via `Practice.allows_free_form_items` (off by default) — therapy/coaching practices are unaffected
- ✅ Free-form-items practices bill company/non-individual counterparties as a plain `Client` row without therapy-only friction — the client form hides date-of-birth/insurance/hourly-rate/GebüH fields, and the dashboard no longer flags a session-less client as permanently "needs attention"

### GebüH Billing (P-046)
- ✅ `GebuhZiffer` catalogue — 9 seeded Ziffern (1, 4, 19.1–19.6, 19.8) with Höchstsatz/Mindestsatz, frequency constraints, and Alleinleistung notes
- ✅ `Leistungserfassung` model — per-session GebüH service lines; `betrag` and `vereinbarter_betrag` frozen at entry time
- ✅ `Client.needs_gebueh_invoice` flag — gates all GebüH features per client (PKV/Beihilfe clients only)
- ✅ Quick-entry form (`/gebueh/`) — checkbox list per session, <30 seconds to record; soft warnings for frequency overruns and Alleinleistung conflicts (Ziffer 4)
- ✅ Session row chips — recorded Ziffer numbers shown inline in the Sitzungen tab
- ✅ Invoice PDF — conditional GebüH block: Diagnose line, per-visit headline row (date, service, amount) with Ziffer/Restbetrag collapsed into a muted detail line underneath; running "GebüH gesamt" total near the grand total; unchanged layout for non-GebüH clients
- ✅ Invoice detail page (web view) mirrors the same headline-row + collapsed detail-line layout as the PDF, instead of a separate row per code plus subtotal/remaining rows; totals block also shows the running "GebüH gesamt" alongside the invoice grand total, matching the PDF
- ✅ Recorded Ziffer amount capped at what's actually charged (`min(satz_max, vereinbarter_betrag)`) rather than always showing the code's ceiling rate
- ✅ Probatorik callout — Overview tab hint when diagnosis not yet set; escalates to warning badge after 5+ diagnostic Ziffern recorded
- ✅ `Client.gebueh_no_diagnosis` opt-out — per-client checkbox to omit the diagnosis line from GebüH invoices (PDF and web invoice detail) while keeping the Ziffern/fee-schedule breakdown

### Session Tracking
- ✅ Historical session data import
- ✅ Monthly session aggregation
- ✅ Duration tracking (15/60/90/120 minutes)
- ✅ Service type classification
- ✅ Cancellation tracking (`Session.cancelled` field — source of truth for capacity analytics)
- ✅ Group session support (`Session.group_size` — therapist-hour normalisation)
- ✅ Short sessions (e.g. 15-min Check-In) billed pro-rata from the 60-min rate (`hourly_rate_60 * duration/60`) instead of the full hourly rate; 90-min+ sessions keep their own negotiated flat rate
- ✅ Billable toggle (`Session.billable`) — excludes intro calls or non-billable sessions from all billing calculations; toggle button in protocol tab
- ✅ Interactive heatmap visualization
- ✅ Delete unbilled session from client detail (blocked if already invoiced)

---

## 📊 Analytics & Reporting

### Dashboard (P-117, narrowed further in P-050 phase 4)
- ✅ Stats strip — year revenue, year profit, outstanding invoices (count + total, highlights in red), time off with current/upcoming holiday hint
- ✅ Quick-action buttons — "+ New invoice" / "+ New client" top-right of stats strip
- ✅ **This Week widget** — `WeeklyFocusWidgetBuilder` shows this week's sessions (Mon–Sun) plus tasks due today or overdue, sharing the Focus Queue's `due_date` signal (P-028, merged into `due_date` in P-050)
- ✅ Capacity monitoring widget — conditional, only shown once a monthly target is configured
- ✅ Status breakdown (Draft/Sent/Paid/Cancelled) — all-time overview
- ✅ Recent invoices overview
- ✅ Multi-practice overview cards — shown only when the user has access to more than one practice
- ✅ Dark mode + Privacy mode
- ℹ️ The dashboard is a pure overview now — the old "Needs Action" queue and separate daily-agenda pane were retired in P-050 phase 4; that working surface is the [Focus Queue](#focus-queue-p-050) (`/focus/`), and revenue trends live on the Analytics page

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
- ✅ Learned auto-categorization — bank-sourced expenses are pre-filled with the category last assigned to the same counterparty (by IBAN, falling back to payer name); the mapping is learned automatically whenever a category is assigned or corrected via the bank-import review screen or the expense edit form

### Time Off Management
- ✅ Vacation/Sick leave/Holiday tracking
- ✅ Date range with duration calculation
- ✅ Year-spanning periods supported
- ✅ Workday calculations — real Berlin public holidays (`DateRangeHelper.count_working_days`), not the old 5/7 calendar approximation; "Duration"/"Wk." columns relabeled "workdays"/"Arbeitstage" to match
- ✅ Capacity impact analysis
- ✅ Period-based calculations
- ✅ Calendar integration
- ✅ In-app create/edit/delete (`/timeoff/`) — no longer admin-only; list splits into upcoming/current vs. past (P-121)
- ✅ Multi-period heads-up email to clients — select any combination of upcoming periods, editable bilingual (DE/EN) preview with per-client personalized salutation; recipient table (client code, language, last/next session) with a select/unselect-all toggle for quickly trimming a long list; subject/body are date-only ("24-28th July" / "Fri 24th - Tue 28th July") so clients see what's affected without needing to know what the time off is for (P-121)

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
- ✅ Bank statement import (`/bank/import`): delimiter and column names are configurable per practice (Practice admin settings), defaulting to GLS Bank's export format — other banks' CSV exports work without touching code (issue #11)
- ✅ "Overdue after" threshold is a per-practice setting (`Practice.overdue_after_days`, default 30) instead of a hardcoded value — controls the dashboard's overdue-invoice widget, the Focus Queue's unpaid-invoice task, and the client detail page's payment-reminder urgency (issue #195)

### Google Calendar Integration (Phase 1-5 - Complete ✅)

#### Phase 1-2: Foundation
- ✅ OAuth2 authentication with token storage
- ✅ Calendar event import from "Praxis" calendar
- ✅ Automatic client matching via client codes
- ✅ Service type mapping based on duration (15/20/60/90 min)
- ✅ Cancellation detection with "(cancel)" keyword
- ✅ Reinstatement: un-cancelling an event in Google Calendar restores the Session on next fetch, refreshing its date/time/duration in the same step
- ✅ Two-miss cancellation debounce: a session is only auto-cancelled after its calendar event is missing on two consecutive fetches, avoiding false cancellations from transient Google API gaps

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
- ✅ Bilingual app UI (German/English) with a DE/EN language switcher — every template, view, model, and admin label wrapped via Django i18n (P-039)
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
- ✅ Draft autosave + unsaved-changes warning on long-text forms (session logs, client case notes) — protects against accidental back/forward navigation wiping out typed content

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
- ✅ 1,400+ automated tests
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
- ✅ [P-042 Multi-practice tax allocation](projects/done/P-042_TAX_MULTI_PRACTICE_ALLOCATION.md) — guide + in-app split calculator for splitting daily pauschalen across multiple EÜR

### Developer Documentation
- ✅ CHANGELOG.md (comprehensive)
- ✅ CODE_STRUCTURE.md
- ✅ PERFORMANCE.md
- ✅ SCRIPTS.md
- ✅ FEATURES.md (this document)

### Code Documentation
- ✅ Docstrings on all functions
- ✅ Inline comments for complex logic
- ✅ Type hints (partial)
- ✅ Example usage in docstrings

---

## ❌ Not Planned

Features explicitly out of scope:
- Complex accounting (use dedicated software)
- Insurance billing (German system)
- Video conferencing
- Payment processing (online payments)

For planned and in-progress work see [PROJECTS.md](../PROJECTS.md) and [docs/projects/](projects/).

---

## 🐳 Self-hosting

- ✅ Pre-built multi-arch Docker image (`amd64` + `arm64`) published to GHCR — ~157 MB (down from ~260 MB as of v0.5.1, via a multi-stage build that keeps the Pillow compiler toolchain out of the shipped image)
- ✅ `prod.py` — one-command setup: generates secrets, pulls image, starts stack, walks through login + practice creation
- ✅ `docker-compose.prod.yml` — production compose file; downloaded automatically by `prod.py setup`
- ✅ Version-pinned: `prod.py` and `docker-compose.prod.yml` always match; `update` notifies when a newer `prod.py` is available
- ✅ In-app update banner — checks GitHub releases once per day; shows a dismissible banner when a newer release is available; opt-out via `UPDATE_CHECK_DISABLED=true`

Last Updated: 20 August 2026
