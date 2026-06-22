# Changelog - Payments System

Major features and milestones in chronological order.

## 2026-06-22 — v0.2.2 patch release

- **Bug fix**: creating a new inquiry failed with "Sprache: Dieses Feld ist zwingend erforderlich" — the `language` field was in the form's `Meta.fields` but never rendered in `inquiry_form.html`. Added it between `source` and `status`.
- **i18n foundation** (P-039): initial DE/EN `.po` catalogs committed; `compilemessages` now runs during Docker image build so translations ship with the image.
- **Nav consolidation**: Abrechnung moved into the Rechnungen dropdown; Bank-Import and Analysen moved into a Finanzen dropdown. Reduces top-level nav items from 11 to 8, fixing overflow on narrow viewports (closes #70).
- **Docs**: stale P-013 "Phase 3 pending" note corrected — all phases were done March 2026.

## 2026-06-18 — v0.2.1 patch release

- **Bug fix**: weekly focus widget crashed with `NoReverseMatch` when a focus task was rendered — URL name was `todo_toggle_complete` (function name) instead of `todo_toggle` (registered name).
- **Bug fix**: `.warning-box` rendered as a neutral grey panel instead of a warning-coloured box — a duplicate `@layer components` definition added during the `common.css` migration was overriding `background`, `color`, padding, and border-radius. Affects delete confirms, email-send warnings, calendar preflight widget.
- **Self-hoster fix** (`prod.py`): image was pulled as `:latest` instead of the pinned version tag, meaning new installs could pull a different image than tested. Both `prod.py` and `docker-compose.prod.yml` now pin to the release tag. Setup also creates a `.gitignore` protecting `.env` (FERNET_KEY), and a backup reminder is shown at setup completion.
- **CSS**: hardcoded hex border-left colors in `info-box`, `alert-box`, `status-box`, `bank-import-status`, `widget-highlight`, `checklist-done-banner` replaced with `--color-*` tokens — dark mode now adapts automatically.
- **In-app update banner**: context processor polls GitHub releases API (24h cache); banner shown to authenticated users when a newer release exists; opt-out via `UPDATE_CHECK_DISABLED=true` in `.env`.
- **Deps**: Node 26-slim, pypdf 6.13.3, GitHub Actions (checkout@6, login@4, build-push@7, qemu@4, buildx@4).
- **Tooling**: reproducible npm builds (`npm ci` + lock file in Dockerfile); `npm audit` added to `./dev.py review`.

## 2026-06-16 — P-024 OSS Release: public at `dholbach/my-practice` (AGPL-3.0, v0.1.0)

- **Public repository**: Orphan snapshot (`895ad65`, "Initial public release v0.1.0") pushed to GitHub with no private dev history. AGPL-3.0 licensed, tagged `v0.1.0`, description + 8 topics set (`django`, `dsgvo`, `gdpr`, `healthcare`, `postgresql`, `practice-management`, `psychotherapy`, `self-hosted`).
- **Contribution onramp** (PR #1): `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, bug/feature issue templates, PR template.
- **Compliance prominence** (PR #2): elevated DPIA / data-security guides for non-technical practitioners.
- **CI + architecture tour** (PR #3, scaled to lint-only in follow-ups): `.github/workflows/ci.yml` runs `ruff check` + `ruff format --check` on push/PR; README gained an architecture tour and badges; AGPL clarified (PR #4).
- P-024 closed; remaining OSS work (first-run wizard, prod docker-compose, pytest/GHCR CI, semver releases, governance) moved to backlog.

## 2026-06-15 — P-045 Phase 2: Tailwind CSS migration (25/29 per-page CSS files)

- **Tailwind pipeline** (Phase 0): `@tailwindcss/cli` in Docker, `--watch=always` sidecar, `tailwind.out.css` in `base.html`, preflight disabled, `@theme` tokens mapped from existing CSS variables.
- **Phase 2 bulk migration**: Deleted 25 of 29 per-page CSS files. All rules moved to `@layer components` in `tailwind.css` (now 1316 lines). Templates updated to remove `{% block extra_css %}` CSS link tags.
- **Conflict handling**: Classes defined differently across multiple files (`.summary-cards`, `.action-btn`) scoped under page wrappers. JS-driven state classes (`.formset-item.deleted`, `.event-row.selected`, `.bulk-actions.visible`) preserved as named classes. Global classes already in `common.css` (`.status-badge`, `.filter-bar`) not re-added.
- **Print styles**: Consolidated from `client_triage.css` and `tax_workday_audit.css` into a single `@media print` block.
- **Bug fix**: Stray `{% endblock %}` in `invoice_detail.html` (leftover from previous session) causing `TemplateSyntaxError` in 4 tests — removed.
- **Remaining**: `widgets.css`, `client_notes.css`, `analytics.css` (multi-session each), `common.css` (Phase 3).

## 2026-06-10 — Calendar reinstatement bugfix

- **`fetch_calendar_events`**: un-cancels Sessions when a previously-cancelled Google Calendar event comes back as active; recovered 24 incorrectly-cancelled sessions caused by a mass-cancellation glitch in late May.

## 2026-06-09 — OSS release prep (P-024)

- Migration squash (87 → 1); SessionHistory exported to CSV then removed; personal tasks/docs gitignored; DPIA template; REINSTALL_CHECKLIST gitignored; README rewritten with motivation + screenshots placeholder; docs/projects cleaned up; 4× InvoiceItem→Session refactors; codebase maintenance (type hints, StyledFormMixin, TimestampedModel, CSS extraction).

## 2026-04-17 — Migration + formatter bugfixes

- **Squashed migration fix**: `0001_0001_squashed` had stale `payments_ap_*` index names in `CreateModel` for `SessionHistory` and `CompanyWithdrawal` — the squash then tried to `RenameIndex`/`RemoveIndex` those same indexes, failing on a fresh DB. Fixed by collapsing CreateModel → final index names and removing the redundant operations.
- **`# fmt: skip` on except-tuples**: ruff format 0.15.x silently strips parens from `except (A, B):` → `except A, B:` (which is `except A as B:` in Python 3). Added `# fmt: skip` to 18 clauses across 7 files; workaround already documented in `pyproject.toml`.

## 2026-04-17 — CVE dependency upgrades (pip-audit)

- **36 CVEs → 0**: All pip-audit findings resolved by upgrading 9 packages:
  - `Django 6.0.3 → 6.0.4`, `cryptography 44.0.2 → 46.0.7`, `pillow 11.1.0 → 12.2.0`
  - `pypdf 5.4.0 → 6.10.2`, `weasyprint 63.1 → 68.1`, `pydyf 0.11.0 → 0.12.1`
  - `pdfplumber 0.11.4 → 0.11.9` (also fixes indirect `pdfminer.six` CVEs)
  - `markdown 3.8 → 3.8.1`, `pytest 8.4.2 → 9.0.3`
- **pytest-asyncio 0.25.2 → 1.3.0**: Required alongside pytest 9 (0.x line had hard `pytest<9`; 1.3.0 relaxes to `pytest<10`). All 773 tests pass.

## 2026-04-17 — P-038 Ph-3 + P-024 pre-flight + pip-audit setup

- **P-038 Phase 3**: Translated all remaining German docs to English; all `.md` files now in English.
- **gitleaks scan**: Historical git scan + `.gitleaks.toml` suppressions for pre-existing placeholder values.
- **Squash migrations**: Migrations 0001–0076 squashed → `0001_0001_squashed`; old files removed.
- **MIT LICENSE**: `LICENSE` file added to repo root.
- **`.env.example` audit**: Verified no real credentials; all placeholders confirmed anonymous.
- **pip-audit**: Added to `requirements.txt` and `./dev.py review` for automated CVE detection.

## 2026-04-17 — P-032 Phases C + D + docs (Phase F)

- **P-032 Phase C**: DB renamed `payments` → `my_practice`, user renamed via temp superuser workaround; docker-compose defaults and `dev.py` hardcodes updated; stale `test_payments` DB dropped.
- **P-032 Phase D**: 7 systemd service/timer files renamed `payments-*` → `my-practice-*` in repo and live (both `/etc/systemd/system/` and `~/.config/systemd/user/`); `install-system-jobs.sh` updated.
- **P-032 Phase F**: Operational docs updated — `BACKUP_SETUP.md`, `REINSTALL_CHECKLIST.md`, `SCRIPTS.md`, `SECURITY.md`, `CODEBASE_STANDARDS.md` all use new names/env vars. Phase E (repo folder rename) deferred to P-024.

## 2026-04-17 — P-032 Phase B + Codebase Review Tooling

- **P-032 Phase B**: Docker container names renamed `payments-*` → `my-practice-*`; env var `PAYMENTS_DATA_DIR` → `MY_PRACTICE_DATA_DIR` across `docker-compose.yml`, `dev.py`, `.env.example`.
- **`./dev.py review`**: New monthly/quarterly health-check command — vulture dead-code scan, ruff F401/F841, pip-audit CVE check, pip outdated, coverage report; `--full` adds radon complexity analysis.
- **`docs/guides/CODEBASE_STANDARDS.md`**: Canonical patterns + anti-patterns reference for queries, views, models, templates, JS, language policy, and docs; includes copy-paste scan checklist.
- **Bugfixes**: `except A, B:` → `except (A, B):` fixed across 9 files; `weekly_focus` HTMX branch was unreachable (indentation bug) — fixed; `_expression` parameter renamed in encrypted fields to suppress false vulture warnings.
- **`?next=` round-trip**: `ClientIntakeView`, `InvoiceEditView`, `invoice_delete` all respect `?next=` for post-action navigation.

## 2026-04-14 — Code-Quality-Refactoring + Anfragen-Toggle

- **`BaseClientEmailView`**: Gemeinsames GET/POST-Gerüst (Client-Lookup, Practice-Check, Email-Check, Form-Init/-Validation, Dispatch) in Basisklasse extrahiert. `SendCancellationEmailView`, `SendQuestionnaireEmailView`, `SendContractEmailView`, `SendPaymentReminderView` erben davon; `SendInvoiceEmailView` bleibt standalone. Netto −95 Zeilen.
- **Anfragen-Liste**: Geschlossene Anfragen (converted/declined/unreachable/not_suitable) standardmäßig ausgeblendet; Toggle-Link "Geschlossene anzeigen (N)" / "Geschlossene ausblenden" ergänzt (`?show_closed=1`).
- **ruff-Format**: Projektweite Formatierung durchgesetzt; u.a. bare Tuple-Form in `except`-Klauseln (`except A, B:` statt `(A, B)`), unused import in `weekly_focus_widget.py` entfernt.
- **FEATURES.md**: Abschnitt "Client Inquiries & Lead Tracking" ergänzt (P-031 + P-034 waren bisher nicht dokumentiert).

## 2026-04-13 — Docs-Reorganisation + P-024 PII-Bereinigung

- **Docs-Struktur**: `docs/development/` aufgeteilt in `docs/operations/` (Housekeeping: Backup, Sicherheit, DPIA, Reinstall) und `docs/notes/` (Analysen, Workarounds, Status-Snapshots); `docs/README.md` aktualisiert; Root-`README.md` entrümpelt (keine persönlichen Stats mehr).
- **P-024 PII-Bereinigung**: Echte Name, IBAN, Steuernummer, Adresse, E-Mail aus `Practice`-Modell-Defaults und Migration `0005_practice.py` entfernt; Projekt-Datei nach `P-024_OSS_RELEASE.md` umbenannt.
- **CLAUDE.md**: Neue Dokumentations-Sektionen `operations/` und `notes/` dokumentiert.

## 2026-04-13 — Feiertags-bereinigte Werktags-Berechnung (M-PAT-05)

- **`DateRangeHelper.count_working_days`**: Neuer optionaler `holidays`-Parameter (`set[date] | frozenset[date]`); Feiertage werden zusätzlich zu Wochenenden ausgeschlossen. Abwärtskompatibel (Default = leer).
- **`capacity_helpers.py`**: `calculate_period_capacity`, `_calculate_weighted_capacity` und `get_capacity_trends` nutzen jetzt Berlin-Feiertage statt reiner Mon–Fr-Zählung; `round(days * 5/7)`-Approximation in `get_capacity_trends` durch exakte `count_working_days`-Aufrufe ersetzt.
- **`timeoff_helpers.py`**: `calculate_timeoff_for_period` und `calculate_timeoff_for_year` zählen Ausfall-Werktage feiertags-bereinigt.
- **Anfragen-Analytics (`/inquiries/`)**: Ø Wartezeit pro Stage jetzt in Werktagen (Mon–Fr, ohne Berlin-Feiertage) statt Kalendertagen; DB-seitige `Avg(DurationField)` durch Python-seitige `count_working_days`-Berechnung ersetzt; UI-Label „Tage" → „Werktage".
- **Copilot-Instructions**: M-PAT-05 dokumentiert das kanonische Muster für Werktags-Berechnungen.
- **Tests**: `test_timeoff_helpers` und `test_practice_analysis` angepasst an feiertags-bereinigte Erwartungswerte.

## 2026-04-12 — P-034 Anfragen-Analytics + Meilenstein-Dates

- **4 Milestone-DateFields** auf `ClientInquiry`: `contacted_date`, `intro_date`, `intake_date`, `converted_date` (alle nullable). Migration 0070.
- **Auto-Fill**: `InquiryForm.save()` setzt das passende Datum automatisch, wenn Status auf CONTACTED / INTRO_MEETING / IN_INTAKE wechselt und das Feld noch leer ist.
- **Convert-Auto-Date**: `InquiryConvertView` setzt `converted_date = date.today()` beim Aufnehmen.
- **Auswertungs-Panel** auf `/inquiries/` (einklappbar): Pipeline-Funnel (Anzahl pro Stage), Ø Wartezeit pro Transition (nur wenn Datumsdaten vorliegen), Quellen-Breakdown mit Balkendiagramm, Monats-Trend (letzte 12 Monate via `TruncMonth`).
- **Code-Qualität**: `InvoiceQuerySet` mit `.with_client()`, `.with_items()`, `.paid_in_year()`, `.in_year()`; `_make_from_email()` + `_dispatch_email()` Helpers in `email_views.py`; Python-3-Exception-Syntax mit `# fmt: skip`-Guards gegen ruff-formatter-Bug; `pep8` → `pycodestyle`.

## 2026-04-02 — Session delete + mypy 1.20 type fixes

- **Session löschen**: Neue `session_delete`-View (`POST clients/<pk>/sessions/<session_pk>/delete-session/`); geblockt wenn Sitzung bereits abgerechnet (`InvoiceItem` vorhanden); `SessionLog` kaskadiert automatisch; 🗑️-Button im Protokoll-Tab für unberechnete Sitzungen ohne Log-Eintrag
- **mypy 1.20.0 / django-stubs 6.0.2**: Abhängigkeiten upgegraded; `types-Markdown` hinzugefügt; `mypy.ini` `exclude`-Block war unter `[mypy.plugins.django-stubs]` eingetragen statt `[mypy]` — jetzt korrekt; 0 Fehler auf 103 Quelldateien
- **Echte Bugs behoben**: `update_client_tags` nutzte `InvoiceItem.session_date` (existiert nicht, richtig: `session__session_date`); `check_media` nutzte veraltetes `CompanyExpense.receipt`-Feld (jetzt `receipts` Reverse-FK)

## 2026-04-02 — Code-Quality Refactoring (no new features)

- **Exception syntax**: Fixed 19 Python 2-style `except A, B:` → `except (A, B):` across 10 files
- **Type hints**: Removed all `Dict`, `List`, `Optional`, `Tuple`, `Union` imports from `typing` across 10 files; replaced with built-in Python 3.10+ syntax (`dict`, `list`, `X | None`, etc.)
- **Public API**: Renamed `RevenueCalculator._build_paid_date_filter` → `build_paid_date_filter` (wasn't private, was called externally in 2 views)
- **N+1 fix**: `TagListView` — replaced per-tag `.clients.count()` loop with `Count("clients")` annotation in `get_queryset()`
- **`StyledFormMixin`**: Applied to `InvoiceForm`, `InvoiceItemForm`, `InvoiceEmailForm` — removed all manual `class="form-control"` widget attrs
- **`DateFormField`**: Applied to all date fields in `InvoiceForm` and `InvoiceItemForm`
- **`TimestampedModel`**: 7 models (`Invoice`, `CompanyWithdrawal`, `CompanyExpense`, `TimeOff`, `Client`, `ClientTag`, `GoogleCalendarToken`) now inherit the base instead of duplicating `created_at`/`updated_at`
- **P-035 complete**: `report_monthly_sessions.py` switched from `"Ausfall" not in description` to `not item.session.cancelled` — last remaining P-035 follow-up item resolved
- **Bankimport badges**: `auto-withdrawal` → "💸 Entnahme", `auto-expense` → "📋 Ausgabe" in `bank_import.html`; no longer shown as red "? Offen"

---

## 2026-04-01 — P-036 Calendar→Session Decoupled Flow

**Phase 1 — Auto-create Sessions on fetch:**
- `fetch_calendar_events` now calls `Session.objects.get_or_create()` for matched clients immediately on new event ingestion — sessions appear in the Protokoll tab before billing approval
- `PendingCalendarEvent.session` OneToOneField (nullable) links the queue event to its auto-created `Session`
- Migration `0066_pendingcalendarevent_session`

**Phase 2 — 1-click billing from client detail:**
- `bill_session(session, practice)` helper in `calendar_import_helpers.py` — picks up `suggested_service_type` from linked `PendingCalendarEvent`, calculates rate, creates `InvoiceItem` + `PracticeTodo`, guards against double-billing
- `session_bill` POST view at `POST /clients/<pk>/sessions/<session_pk>/bill/`
- Protokoll tab shows "Unberechnet" yellow badge + "🧾 Zur Rechnung" button on sessions without `InvoiceItem`

**Phase 3 — `/calendar/import/` noise reduction:**
- Events with `PendingCalendarEvent.status=IMPORTED` are filtered out of the list
- "✓ Bereits importiert" stat card shows hidden count for transparency

---

## 2026-04-02 — P-030 Session Collapse + P-033 E-Mail-Textbausteine

**P-030 Session List Collapse:**
- `client_detail.html`: erste 10 Protokolleinträge sichtbar, Rest in `<div id="cn-old-entries" class="cn-collapsed-hidden">` versteckt
- Toggle-Button mit Zähler ("Ältere Einträge anzeigen (N mehr)") über `cnToggleOldEntries()` JS-Funktion
- `client_notes.css`: `.cn-old-toggle` Stil für den Toggle-Button

**P-033 E-Mail-Textbausteine:**
- Neue Seite `/tools/boilerplate/` (`boilerplate_view` in `operational_views.py`)
- 6 zweisprachige Textkarten (DE/EN): Erstgespräch, Keine Kassenerstattung, Warteliste, Terminabsage, Therapieende, Rechnung
- Copy-Button per Karte via `navigator.clipboard.writeText`; Tab-Umschalter DE/EN pro Karte
- Nav-Link „✉️ E-Mail-Textbausteine" im ⚙️-Admin-Dropdown in `base.html`
- `boilerplate.css` + `boilerplate.html` neu erstellt

---

## 2026-03-31 — M-14 Badge-Token-System + P-016 Docs

**M-14 (P-016 CSS-Tokens):**
- 12 semantische Badge-Farb-Tokens in `common.css` (`--badge-{neutral|muted|blue|indigo|green|yellow|amber|orange|pink|purple|violet|red}-{bg|text|border}`) — light + dark je in `:root` / `[data-theme="dark"]` definiert
- `inquiry_list.css` refaktoriert: 18 `[data-theme="dark"]`-Overrides entfernt; alle `.source-*` und `.status-*` Badge-Klassen nutzen jetzt Tokens; `.empty-state`-Duplikat entfernt
- Neue Seiten mit farbigen Badges brauchen kein eigenes Dark-Mode-Override mehr

**P-016 Docs-Bereinigung:**
- `todo/P-016_MODERNISATION.md` in TODO/WIP/DONE-Struktur umgebaut (Medium/Low Prio getrennt)
- Veraltetes `done/P-016_MODERNISATION.md` gelöscht (History jetzt in DONE-Tabelle im todo-Dok)
- PROJECTS.md: P-016-Backlog-Eintrag konsolidiert + Link zum todo-Dok; P-032 (Projekt-Umbenennung, low prio) als neuer Backlog-Eintrag

---

## 2026-03-31 - Gardening-Session

**Docs-Catch-up:**
- Done-Docs erstellt für P-017, P-018, P-019, P-021, P-022, P-025, P-026
- FEATURES.md um P-025/026/027 ergänzt; stray-Header bereinigt
- `## 🌿 Gardening`-Abschnitt in TODO.md wiederhergestellt + dauerhaft geschützt (copilot-instructions.md)
- P-027-Status-Header auf "DONE (2026-03-27)" korrigiert

**4 Quick-Fixes:**
- **Fahrtkosten (P-027)**: `tax_views.py` berechnet `fahrtkosten_deduction` separat und zieht es von `gross_profit` ab; Zeile in Zusammenfassungs-Tabelle ergänzt
- **Stundensatz**: nur 60-min-Rate im Klienten-Header (90-min-Anzeige entfernt)
- **Notfallkontakte Dark Mode**: explizites `color: var(--text-primary)` auf Kontakt-Divs
- **Chart-Overflow**: `overflow: hidden` auf `.chart-wrapper` in `common.css`

---

## 2026-03-30 - P-031 Client Inquiries / Lead Tracking ✅

**ClientInquiry model:**
- `ClientInquiry` Modell mit `InquirySource` + `InquiryStatus` StrEnums (praxis-gescoped)
- CRUD-Views: List, Create, Update, Delete, Convert-to-Client
- `InquiryConvertView`: erstellt `Client` aus Anfrage, setzt `status=CONVERTED`
- Templates: `inquiry_list.html`, `inquiry_form.html`, confirm_delete, convert_confirm
- Nav-Link + Block in `client_detail.html`; `inquiry_list.css` mit Status/Source-Badges
- `ClientInquiryAdmin`; Migrationen 0060–0062
- Tests: `test_inquiry.py` — volle CRUD-Coverage; 22+ Tests grün

**P-031 Post-Launch-Erweiterungen:**
- `inquiry_date` default heute (kein leeres Feld beim Erstellen)
- Neue Quelle `ITS_COMPLICATED` ("It's Complicated") mit Amber-Badge; Migration 0063
- `MarketingPeriod` Modell (praxis-gescoped, start/end/description, `is_active()`); aktive Zeiträume als Badge-Leiste auf `/inquiries/`; `MarketingPeriodAdmin`
- Neuer Status `NOT_SUITABLE` ("Kein Match") für unqualified leads; terminal; Migration 0064
- Sensitive Data: `full_name`, `email`, `phone` in `<span class="sensitive-data">` — globaler Privacy-Modus; 🔒-Icon auf Spaltenköpfen via `.th-sensitive::after`

**Security:**
- `PIIExceptionReporterFilter`: schwärzt PII-Felder in Django 500-Tracebacks (`full_name`, `email`, `phone`, `address`)

**Files:**
- `app/my_practice/models/inquiry.py` — ClientInquiry, InquirySource, InquiryStatus, MarketingPeriod
- `app/my_practice/views/inquiry_views.py`
- `app/templates/my_practice/inquiry_list.html`, `inquiry_form.html`
- `app/static/css/inquiry_list.css` — dark-mode badge overrides included
- `app/my_practice/migrations/0060_*` through `0064_*`
- `app/my_practice/tests/test_inquiry.py`

## 2026-03-30 - CSS Dark Mode + Docs Cleanup ✅

**CSS dark mode improvements:**
- `common.css`: Added `--text-muted` CSS variable (`#718096` light / `#94a3b8` dark)
- `common.css`: `[data-theme="dark"]` overrides for `.status-badge` (draft/sent/paid/cancelled)
- `inquiry_list.css`: `[data-theme="dark"]` overrides for all 8 source badges + 9 status badges

**Docs cleanup:**
- `PROJECTS.md`: Trimmed to last 2 Recent Activity entries + clean backlog + completion table
- `TODO.md`: Rewritten as active-only backlog (~45 lines); all historical ✅ content removed
- `.github/copilot-instructions.md`: Added "Documentation Gardening" section with done-item graduation workflow + gardening checklist

## 2026-03-27 - Anamnesebogen + Behandlungsvertrag per E-Mail ✅

**SendQuestionnaireEmailView:**
- ✅ Anamnesebogen .docx als E-Mail-Anhang versenden — GET zeigt bearbeitbares Formular mit vorausgefülltem Betreff/Textkörper
- ✅ Datei aus `PAYMENTS_DATA_DIR/documents/Anamnesebogen.docx` (DE) oder `Anamnesebogen (eng).docx` (EN) nach `client.language`
- ✅ Setzt `client.questionnaire_sent_date` automatisch nach erfolgreichem Versand
- ✅ Verknüpft mit Onboarding-Stepper auf Klienten-Detailseite

**SendContractEmailView:**
- ✅ Behandlungsvertrag PDF wird zur Laufzeit generiert (WeasyPrint) und als Anhang versendet
- ✅ GET zeigt bearbeitbares Formular; Dateiname nach Sprache: `Behandlungsvertrag_{code}.pdf` / `TreatmentContract_{code}.pdf`
- ✅ `generate_contract_pdf_bytes(client, practice, lang)` als gemeinsamer Helper aus `api_views` extrahiert

**Code-Qualität (Cleanup-Pass):**
- ✅ `email_utils.py`: moderne Python-3.13-Typen (`dict`, `str | None` statt `Dict`, `Optional`)
- ✅ `email_views.py`: ungenutzte Imports entfernt; `_generate_pdf` Duplikat durch Delegation an `_prepare_practice_images` + `_render_invoice_pdf_bytes` ersetzt; alle Flash-Messages auf Deutsch
- ✅ `settings.py`: `DEBUG`-Default auf `"False"` korrigiert; veraltetes `SECURE_BROWSER_XSS_FILTER` entfernt
- ✅ `views/__init__.py`: `__all__` bereinigt — `SendQuestionnaireEmailView` unter `# Email views`; Bank-Views ergänzt; `# noqa: F401` entfernt
- ✅ `urls.py`: toten Kommentar entfernt

**Files:**
- `app/my_practice/views/email_views.py` — `SendQuestionnaireEmailView`, `SendContractEmailView`
- `app/my_practice/views/api_views.py` — `generate_contract_pdf_bytes()` extrahiert
- `app/my_practice/utils/email_utils.py` — `get_questionnaire_email_content`, `get_contract_email_content`
- `app/templates/my_practice/send_questionnaire_email.html`
- `app/templates/my_practice/send_contract_email.html`
- `app/my_practice/urls.py` — Routen `clients/<pk>/send-questionnaire/`, `clients/<pk>/send-contract/`

**group_size on InvoiceItem (data quality):**
- ✅ New `group_size` field — group sessions count once for the therapist regardless of participants
- ✅ Migration with RunPython data backfill
- ✅ `count_sessions(therapist_hours=True)` param added to toggle per-therapist counting
- ✅ All analytics callers updated; admin InvoiceItemInline updated

**Analytics UI:**
- ✅ Stärkste Monate: revenue column, per-year colour badges, grid-based bar chart, top 20, sorted by revenue
- ✅ Saisonalität section: avg capacity % per calendar month, grid bars, derived from existing capacity_trends (no extra query)
- ✅ Jahresvergleich chart: monthly therapist hours overlaid per year, last 4 years + average line
- ✅ Year colour palette: newest = most assertive (amber 2026 → emerald 2025 → sky 2024 → violet 2023 → teal → slate → dark-grey); CSS custom properties — single source of truth

**Deduplication / CSS cleanup:**
- ✅ `.chart-wrapper` class for all canvas containers
- ✅ `.timeoff-stat` / `.timeoff-stat-value` / `.timeoff-stat-label` for TimeOff summary boxes
- ✅ `.tab-content > h2:first-child { margin-top: 0 }` replaces 5× inline style
- ✅ `class="chart-subtitle"` replaces 8× inline `<p style="...">` subtitle tags
- ✅ `.top-clients-table` merged into existing `.client-table`; `.rank` / `.revenue-amount` as standalone helpers
- ✅ `_get_year_financials()` module helper eliminates duplicated queryset logic in RevenueAnalyzer and ProfitCalculator
- ✅ `_common_kwargs` property on AnalyticsDashboardBuilder eliminates repeated 4-kwarg blocks
- ✅ `_TIMEOFF_ZERO` class attribute replaces two identical early-return dicts in `_get_timeoff_data`
- ✅ `timedelta` hoisted to top-level import in capacity_helpers.py; removed 4 local imports / `__import__` hacks

**Files:**
- `app/my_practice/models/invoice.py` — group_size field
- `app/my_practice/admin.py` — group_size in InvoiceItemInline
- `app/my_practice/migrations/0046_invoiceitem_group_size.py`
- `app/my_practice/utils/calculations.py` — therapist_hours param
- `app/my_practice/utils/analytics_utils.py` — _get_year_financials, refactored yearly loops, Ausfall removed from revenue
- `app/my_practice/utils/analytics_dashboard_builder.py` — _TIMEOFF_ZERO, _common_kwargs, seasonality, Jahresvergleich
- `app/my_practice/utils/capacity_helpers.py` — timedelta cleanup, month_num in output
- `app/my_practice/utils/dashboard_widgets.py` — therapist_hours=True
- `app/templates/my_practice/analytics.html` — grid bars, chart-wrapper, chart-subtitle, timeoff-stat
- `app/static/css/analytics.css` — CSS custom properties for year colours, .chart-wrapper, .timeoff-stat, .tab-content h2

## 2026-03-16 - Bank Review: Invoice Selection Tally ✅

**UX Improvement — `/bank/review/`:**
- ✅ Live tally when multi-selecting invoices in manual-match form
- ✅ Shows count + sum of selected invoices immediately below the `<select>`
- ✅ Green highlight when total matches transaction amount (within €0.01)
- ✅ Orange highlight with explicit difference when totals don't match
- ✅ Hides automatically when nothing is selected

**Files:**
- `app/static/js/bank_review.js` — new JS module (IIFE, no dependencies)
- `app/templates/my_practice/bank_review.html` — `data-amount` on form + `extra_js` block

## 2026-02-17 - Security Foundation Progress (P-011) 🔄

**System Security Milestone:**
- ✅ Laptop neu installiert
- ✅ Full Disk Encryption (LUKS) aktiv
- ✅ Secure Boot aktiviert

**Documentation Updates:**
- ✅ Reinstall-Dokumentation um aktuellen Ist-Stand ergänzt
- ✅ Konkrete Restschritte nach Neuinstallation dokumentiert (Services, Backup, Restore-Smoketest, Security-Check)
- ✅ P-011 von TODO nach WIP überführt (Projektstatus angepasst)

**Next Security Steps (Open):**
- [ ] Backup Encryption (Phase 2)
- [ ] DPIA Dokumentation (Phase 3)
- [ ] Optional: Field Encryption für klinische Notizen (Phase 4)

## 2026-02-16 - Dark Theme Contrast Improvements ✅

**UI/UX Fixes:**
- ✅ Fixed dark-on-dark contrast issues in Dark Theme
- ✅ Added `color: var(--text-primary)` to 14 critical UI components
- ✅ Improved readability for: agenda items, client cards, widgets, analytics, expenses
- ✅ All text now properly visible in both Light and Dark themes
- ✅ Privacy Mode compatible

**Affected Components:**
- Dashboard agenda items (`.agenda-title`, `.agenda-content`)
- Client cards (`.client-card`, `.card-title`, `.client-workflow-stats`)
- Widget system (`.widget-list-item`, `.widget-pill`)
- Analytics metrics (`.metric-card`)
- Common components (`.card`, `.section-card`, `.info-card`, `.timeline-content`, `.chart-wrapper`)
- Expense categories (`.category-card`)

**Developer Tools Added:**
- `scripts/check_dark_theme_contrast.py` - Static CSS analysis (finds 83 potential issues)
- `scripts/browser_contrast_tester.js` - Runtime WCAG contrast checker
- `docs/development/DARK_THEME_CONTRAST_ISSUES.md` - Documentation & guidelines

**Testing:**
- ✅ Light theme verified (no regressions)
- ✅ Dark theme contrast validated
- ✅ Privacy mode tested
- ✅ Hover states confirmed

## 2026-02-01 - Dependency Updates & Code Cleanup ✅

**Major Version Updates:**
- Python 3.12 → 3.13.1 (5-10% performance improvement)
- Django 5.0.1 → 5.1.6 (async queries, better type hints, improved admin)
- gunicorn 21.2.0 → 23.0.0 (better async support)
- weasyprint 57.1 → 63.1 (better font handling, CSS improvements)
- ruff 0.8.4 → 0.9.2 (more linting rules, better performance)
- Google API packages updated (security fixes)
- ⏸️ PostgreSQL 15 (kept) - PG17 upgrade deferred to Q2 2026 (requires data migration)

**Code Cleanup:**
- ✅ Removed debug logging from InvoiceEditView (form errors now display correctly)
- ✅ Eliminated wrapper functions in expense/withdrawal views (~40 lines removed)
- ✅ URLs now use CBVs directly (ExpenseCreateView.as_view())
- ✅ Cleaner code, consistent with Django best practices

**Testing:**
- ✅ All 608 tests passing with new versions
- ✅ Invoice PDF generation verified (WeasyPrint 63.1)
- ✅ Google Calendar OAuth flow tested
- ✅ Multi-practice functionality confirmed
- ✅ Admin interface working correctly

**Performance Improvements:**
- ~5-10% faster execution (Python 3.13)
- Better async support for future enhancements
- Improved query optimization (Django 5.1)

---

## 2026-02-01 - Multi-Practice CRUD Refactoring Complete ✅

**Major Architecture Improvement: Consistent Practice-Scoped Views**

### New Base Classes
- ✅ **PracticeScopedCreateView**: Auto-assigns practice on save, unified success messages
- ✅ **PracticeScopedUpdateView**: Auto-filters queryset by practice, prevents cross-practice access
- ✅ **PracticeScopedListView**: Auto-filters lists by current practice
- ✅ All base classes support `.format(obj=instance)` in success messages

### Migrated Views (from FormCreateViewMixin/FormUpdateViewMixin)
- ✅ **ClientIntakeView** → PracticeScopedUpdateView (~40 lines → ~20 lines)
- ✅ **WithdrawalCreateView/UpdateView** → PracticeScopedCreate/UpdateView
- ✅ **ExpenseCreateView/UpdateView** → PracticeScopedCreate/UpdateView
- ✅ **InvoiceCreateView** → PracticeScopedCreateView
- ✅ **InvoiceEditView** → PracticeScopedUpdateView with enhanced error display

### Error Handling Improvements
- ✅ **InvoiceEditView**: Now shows specific field errors instead of generic "Bitte korrigieren Sie die Fehler im Formular."
- ✅ **Formset Errors**: Display with item numbers (Item 1, Item 2, etc.) for clarity
- ✅ **Field Labels**: Error messages include field labels for better UX

### Invoice Forms Enhancement
- ✅ **Practice-Scoped Client Filtering**: InvoiceForm now respects current practice context
- ✅ **Practice-Scoped ServiceType Filtering**: InvoiceItemForm uses `.for_current_practice_with_globals()`
- ✅ **Request Context**: Forms receive request parameter for practice-aware queries
- ✅ **Factory Function**: `get_invoice_item_formset(request)` passes request to all formset forms

### Manager Extensions
- ✅ **for_current_practice_with_globals()**: New manager method for ServiceType and similar models
- ✅ Allows global items (practice=NULL) to be available across all practices
- ✅ Used for default service types (therapy_60, cancellation, etc.)

### Test Coverage
- ✅ **test_practice_isolation.py**: 6 tests validating multi-practice data separation
- ✅ **test_template_validation.py**: 6 tests preventing template/form field mismatches
- ✅ **test_helpers.py**: Updated with get_or_create() pattern to prevent duplicate key errors
- ✅ **Admin Tests**: Fixed client creation test to include required practice field
- ✅ All 608 tests passing

### Database Migrations
- ✅ **0029_assign_clients_to_default_practice**: Assigns existing clients to default practice
- ✅ **0030_assign_all_data_to_default_practice**: Assigns invoices, expenses, withdrawals, service types
- ✅ **0031_add_kleinunternehmer_option**: Adds Kleinunternehmer vs. Heilpraktiker tax options

### Practice Model Enhancements
- ✅ **is_kleinunternehmer**: Toggle between §19 UStG (Kleinunternehmer) and §4 Nr.14 UStG (Heilpraktiker)
- ✅ **kleinunternehmer_text_de/en**: Separate text for Kleinunternehmer invoices
- ✅ **Invoice PDFs**: Conditional VAT text rendering based on is_kleinunternehmer flag

### Admin Enhancements
- ✅ **ClientAdmin**: Added practice column and filter
- ✅ **ServiceTypeAdmin**: Shows practice scope (Practice Name or 🌍 GLOBAL)
- ✅ Practice filtering in admin lists for all practice-scoped models

### UI/UX Improvements
- ✅ **Navigation**: Consolidated "Practice Analysis" + "Analytics" → "📊 Analysen" dropdown
- ✅ **Practice Switcher**: Increased dropdown width (350px) and button width (220px) for long practice names
- ✅ **Practice Form**: Added all missing fields (Kleinunternehmer, logo, signature, memberships, payment terms)
- ✅ **Smart Redirects**: Practice switcher redirects to same page in new practice context when appropriate

### Analytics & Dashboard Fixes
- ✅ **Revenue Calculations**: All revenue helpers now support `practice` parameter
- ✅ **Dashboard Queries**: Filter by current practice for all statistics
- ✅ **Heatmap Data**: Practice-scoped session heatmap
- ✅ **Revenue Report**: Practice-filtered invoice lists

### Calendar Integration Fixes
- ✅ **ServiceType Queries**: Use `.for_current_practice_with_globals()` for default types
- ✅ **Event Import**: Pass request context for practice-scoped queries
- ✅ Calendar views respect current practice context

### Code Quality
- ✅ **~50% code reduction** in migrated views (eliminated duplicate practice assignment logic)
- ✅ **Consistent patterns** across all CRUD operations
- ✅ **Type safety** with proper QuerySet filtering
- ✅ **Unused variables removed** in test files for cleaner code

### Breaking Changes
- ⚠️ **Forms**: InvoiceForm and InvoiceItemForm now require `request` kwarg for practice-scoped queries
- ⚠️ **Templates**: Must include `{{ form.practice.as_hidden }}` for practice field
- ⚠️ **Formsets**: Use `get_invoice_item_formset(request)` instead of InvoiceItemFormSet directly

### Migration Notes
- Run migrations: `./dev.py manage migrate`
- Existing data automatically assigned to default practice
- Test with `./dev.py test` (all 608 tests should pass)

---

## 2026-01-31 - Google Calendar Integration: Phase 3-5 Complete ✅

**Feature Complete: Calendar Import with Smart Workflow - Production Ready**

**Phase 3: Approval UI (Complete)**
- ✅ **Smart Auto-Selection**: Ready events (matched client, no duplicate, not cancelled) pre-selected on page load
- ✅ **Status Badges with Tooltips**:
  - ✅ Bereit (green) - Ready to import
  - 🔄 Duplikat (blue) - Already exists as InvoiceItem
  - ⚠️ Unbekannt (orange) - Client not recognized
  - ❌ Cancel (red) - Event cancelled
- ✅ **Manual Overrides**: Change client/service type via dropdowns
- ✅ **Bulk Actions**: Import selected events with one click
- ✅ **Skip Functionality**: Disable unwanted events
- ✅ **Dark Mode Fix**: Labels now visible with correct text colors
- ✅ **Tooltips**: Actions column and skip buttons have helpful descriptions

**Phase 4: InvoiceItem Creation (Complete)**
- ✅ **Duplicate Detection**: Checks if event already exists (same client, date, service type)
- ✅ **Free Vorgespräch**: therapy_free service type creates items with 0€ rate
- ✅ **First Seen Date**: Auto-tracks initial consultation date for new clients
- ✅ **Single Draft Invoice**: One running draft per client (no monthly splits)
- ✅ **Rate Selection**: Automatically uses hourly_rate_60 or hourly_rate_90 based on duration
- ✅ **Comprehensive Error Handling**:
  - Missing client rates validation
  - Duplicate prevention with clear messages
  - German error messages for user clarity
- ✅ **Automatic Client Tracking**: Sets first_seen_date on Vorgespräch import

**Phase 5: Production Polish (Complete)**
- ✅ **Automatic Token Refresh**: Proactive refresh 5 minutes before expiry, handles expired tokens gracefully
- ✅ **API Pagination**: Handles >250 events via Google's nextPageToken system (no limit)
- ✅ **Session Storage**: 30-minute cache for parsed events, reduces API calls on import

**Database Changes:**
- ✅ Migration 0025: Added `first_seen_date` field to Client model
- ✅ Data cleanup: Fixed old initial_consultation items to 0€ rate (ML, AA)
- ✅ Invoice consolidation: Merged duplicate draft invoices

**Service Type Mapping:**
- 15min → therapy_15 (Check-in)
- 20min → therapy_free (Vorgespräch, 0€)
- 60min → therapy_60 (Standardsitzung)
- 90min → therapy_90 (Verlängerte Sitzung)
- Cancelled → therapy_cancelled (Ausfall)

**Commits (12 total):**
1. `28c3015` - Phase 4 Duplicate detection & smart workflow
2. `3d6502a` - Error message improvements
3. `13eacce` - Fix invoice_date field name
4. `8654e45` - Remove currency field
5. `a1cdd51` - Fix hourly_rate_60/90 usage
6. `6aa8374` - Set therapy_free to 0€
7. `d6ae305` - Add first_seen_date field
8. `258bc32` - Single draft invoice per client
9. `0869839` - Documentation updates (FEATURES, TODO, CHANGELOG)
10. `b31ed14` - Multi-Practice architecture plan
11. *(next)* - Phase 5: Token refresh, pagination, caching
12. *(next)* - Documentation update

**Testing:**
- ✅ All 578 tests passing
- ✅ 31 Google Calendar tests passing
- ✅ Real-world testing with ML and AA clients
- ✅ Edge cases: Expired tokens, >250 events, re-import scenarios

**Status:** Production-ready 🚀

---

## 2026-01-31 - Major Cleanup: Reconciliation Infrastructure Removed

**Code Cleanup (~1500+ lines removed):**
- Comprehensive cleanup after reconciliation project completion (96% alignment achieved)
- Removed all obsolete reconciliation infrastructure from production codebase
- Organized documentation into active vs. archive structure

**Deleted Files (~12 files, ~1200+ lines):**
- ✅ `app/my_practice/archive_legacy/` - Entire folder removed
  - `reconciliation_views.py` (266 lines) - Web UI for SessionHistory vs InvoiceItems comparison
  - `reconciliation.py`, `reconciliation_checker.py` - Core reconciliation utilities
  - `historical_reconciliation.py`, `verify_session_alignment.py` - Verification tools
  - Templates: `reconciliation.html`, `historical_reconciliation.html`
  - CSS: `reconciliation.css`
  - Tests: `test_views_reconciliation.py`, `test_reconciliation_checker.py`, `test_reconciliation.py`
  - README.md
- ✅ `app/my_practice/management/commands/check_client.py` - Reconciliation command (obsolete)

**Documentation Organization:**
- ✅ Created `docs/archive/` with comprehensive README
- ✅ Moved completed bugfixes to `docs/archive/bugfixes/` (2 files)
- ✅ Archived reference docs (CALCULATION_PATTERNS_INVENTORY, CODE_DEDUPLICATION_OPPORTUNITIES, FILE_SPLITTING_PLAN, CHART_GENERALIZATION)
- ✅ Updated `TODO.md` - Phase 2 cleanup marked as COMPLETED
- ✅ Created `scripts/archive/README.md` - Comprehensive documentation of 15 archived scripts

**What Remains (By Design):**
- ✅ SessionHistory Model + Admin (permanent historical archive for pre-2026 data)
- ✅ `SESSION_HISTORY_CUTOFF` constant in `heatmap_utils.py` (prevents double-counting)
- ✅ Historical data access in analytics and practice analysis views
- ✅ 15 archived scripts in `scripts/archive/` (documented, kept for reference)

**Test Coverage:**
- ✅ All 578 tests passing after cleanup (44.471s)
- ✅ No regressions introduced

**Impact:**
- Cleaner, more maintainable codebase
- Clear separation: SessionHistory (archive) vs InvoiceItems (active source)
- Better documentation organization
- Easier onboarding for future developers

**See:** [docs/CLEANUP_2026-01-31.md](CLEANUP_2026-01-31.md) for complete details

---

## 2026-01-30 - Phase 2 Migration: Reconciliation Scripts Archiviert

**Code Cleanup:**
- Reconciliation-Projekt offiziell abgeschlossen (96% perfekte Alignment)
- 11 Scripts archiviert in `scripts/archive/` (~2000 Zeilen)
- Archive-Struktur mit README.md erstellt

**Archiviert in `scripts/archive/reconciliation/` (7 Scripts):**
- `monthly_differences.py` - Monatliche Differenzen mit Spreadsheet-Vergleich
- `quick_reconcile.py` - Schneller Top-Klienten-Vergleich
- `deep_reconcile.py` - Detaillierte Diskrepanz-Analyse
- `reconcile_old_vs_new.py` - Monat-für-Monat Vergleich
- `comprehensive_reconciliation.py` - Umfassende Reconciliation-Übersicht
- `bk_monthly_breakdown.py` - Client-spezifischer Breakdown
- `debug_bk_sessions.py` - Debug für Gruppensitzungs-Differenz

**Archiviert in `scripts/archive/completed/` (4 Scripts):**
- `delete_sessionhistory_2026.py` - Einmalige Aufgabe abgeschlossen
- `test_historical_reconciliation.py` - Tests jetzt in my_practice/tests/
- `quick_session_check.py` - Finale Verifizierung abgeschlossen
- `update_cancellation_items.py` - Einmalige Datenmigration abgeschlossen

**Ergebnis:**
- ✅ ~2000 Zeilen Code archiviert (nicht gelöscht - für historische Referenz)
- ✅ Reconciliation-Projekt: 96/103 Clients perfekt aligned
- ✅ 7 verbleibende Diskrepanzen: Gruppensitzungen (absichtlich ausgeschlossen)
- ✅ SessionHistory-Migration Phase 1+2 abgeschlossen

**Aktive Scripts (weiterhin nützlich):**
- `final_reconciliation_report.py` - Historische Dokumentation
- `check_group_sessions.py` - Gruppensitzungs-Verifizierung
- `reconciliation_overview_2025.py` - Finanzübersicht
- `check_2026_payments.py` - Jahr-Übergang-Reporting
- `generate_sessions_table.py` - Session-Report-Generator
- `analyze_sessions_per_client.py` - Klienten-Session-Analyse

**See:** `scripts/archive/README.md` für Details

## 2026-01-30 - Phase 1 Migration: SessionHistory CSV Import Removed

**Code Cleanup:**
- Removed SessionHistory CSV import feature (deprecated since 2026 cutoff)
- Legacy CSV import is complete, historical data (pre-2026) finalized
- InvoiceItems is now the only data source for 2026+

**Changes:**
- **Removed:** `views/import_views/session_history.py` - import_session_history() view (~170 lines)
- **Removed:** `import_forms.py` - SessionHistoryImportForm class (~25 lines)
- **Removed:** `tests/test_imports.py` - Import sanity tests (~60 lines)
- **Removed:** URL route `/import/sessions/`
- **Removed:** Navigation link in base template

**Benefits:**
- Simplified codebase (~255 lines removed)
- Clear data transition: SessionHistory (archive) vs InvoiceItems (active)
- Prevents accidental new SessionHistory entries

**Files Changed:**
- `app/my_practice/views/import_views/session_history.py` - DELETED
- `app/my_practice/tests/test_imports.py` - DELETED
- `app/my_practice/import_forms.py` - SessionHistoryImportForm removed
- `app/my_practice/urls.py` - URL route commented out
- `app/my_practice/views/__init__.py` - Import removed from exports
- `app/templates/base.html` - Navigation link removed

**See:** `docs/SESSIONHISTORY_2026_CUTOFF.md` for full migration plan

## 2026-01-30 - Critical Fix: Session Count Formula Alignment

**Bug Fix:**
- Fixed critical session counting bug in `RevenueCalculator.get_client_sessions_subquery()`
- Subquery was incorrectly using `Sum('quantity')` instead of proper formula `Sum((duration/60) * quantity)`
- Session counts are now normalized to 60-minute base, matching `count_sessions()` utility function

**Impact:**
- Client list view now shows correct session counts (e.g., BK: 85.0→85.5, GM: 64.0→79.0)
- Capacity analysis and practice statistics now use accurate data
- All aggregated client session metrics are now consistent across the application

**Technical Details:**
- Updated subquery to use: `Sum(Cast(F("duration"), FloatField()) / 60.0 * Cast(F("quantity"), FloatField()))`
- Formula: (duration / 60) * quantity = normalized sessions
- Example: 90-minute session = 1.5 sessions, 60-minute = 1.0 session
- Updated test expectations to match correct calculations

**Files Changed:**
- `app/my_practice/utils/revenue_helpers.py` - Fixed `get_client_sessions_subquery()`
- `app/my_practice/tests/test_calculation_consistency.py` - Updated test expectations

## 2026-01-30 - Code Centralization: Revenue Query Deduplication

**Refactoring:**
- Centralized duplicate paid_date filtering logic across the codebase
- Added `RevenueCalculator._build_paid_date_filter()` helper method
- Eliminated code duplication in 4 different locations

**Changes:**
- **New**: `RevenueCalculator._build_paid_date_filter(year, month=None)` - Central Q object builder
- **Updated**: `get_year_revenue()` now uses centralized filter method
- **Updated**: `get_month_revenue()` now uses centralized filter method
- **Updated**: `analytics_utils.py` now delegates to `RevenueCalculator.get_month_revenue()`
- **Updated**: `tax_views.py` now uses centralized filter method
- **Updated**: `analytics_views.py` now uses centralized filter method

**Benefits:**
- Single source of truth for paid_date filtering logic
- Easier to maintain and update filter behavior
- Reduced code duplication from ~25 lines to 1 method call in 4 places
- Consistent behavior across all revenue calculations

**Files Changed:**
- `app/my_practice/utils/revenue_helpers.py` - Added `_build_paid_date_filter()`
- `app/my_practice/analytics_utils.py` - Removed duplicate logic
- `app/my_practice/views/tax_views.py` - Uses central method
- `app/my_practice/views/analytics_views.py` - Uses central method

**Testing:**
- All 629 tests still passing
- No behavioral changes, only code organization

## 2026-01-30 - Revenue Calculation Fix: Dashboard vs. Invoice List Alignment

**Bug Fix:**
- Fixed discrepancy between dashboard monthly revenue and invoice list totals
- Dashboard monthly revenue now uses `paid_date` instead of `invoice_date` for consistency
- **Example**: Invoice list "2026 paid" showed 2300 €, dashboard "Jan 2026" showed 960 €
- **Root cause**: Dashboard filtered by `invoice_date`, invoice list filtered by `paid_date`
- **Resolution**: Updated `RevenueCalculator.get_month_revenue()` to use `paid_date` by default

**Technical Changes:**
- Modified `RevenueCalculator.get_month_revenue(year, month, use_paid_date=True)`
- Added `use_paid_date` parameter with default `True` for tax accuracy
- Falls back to `invoice_date` when `paid_date` is null
- Consistent with `get_year_revenue()` behavior

**Impact:**
- Dashboard monthly revenue now correctly includes invoices paid in that month
- Matches invoice list behavior when filtering by year/status
- Better tax accuracy (counts revenue when actually received)
- All 37 tests still passing

**Files Changed:**
- `app/my_practice/utils/revenue_helpers.py` - Updated `get_month_revenue()`
- `docs/CALCULATION_PATTERNS_INVENTORY.md` - Updated documentation

## 2026-01-08 - SessionHistory 2026 Cutoff + Reconciliation Improvements

**SessionHistory 2026 Cutoff:**
- Removed obsolete `recalculate_session_history` management command
- SessionHistory is now read-only for reconciliation purposes only
- All new session data (2026+) is tracked exclusively in InvoiceItems
- Added deletion script for 2026+ SessionHistory data (`scripts/delete_sessionhistory_2026.py`)
- Updated `verify_session_alignment` to focus on 2025 and earlier data

**Reconciliation System Enhancements:**
- Enhanced `/reconciliation/` view with client selection dropdown
- Added AJAX-powered client verification
- Improved UI with collapsible perfect alignment section
- Added data cutoff info banner explaining SessionHistory scope
- Better visual feedback for discrepancies and perfect alignments

**Capacity Analysis Improvements:**
- Updated practice analysis to focus on live InvoiceItem data
- Improved session counting with centralized `count_sessions()` function
- Better date range handling in capacity calculations

**Email System Updates:**
- Improved email preview functionality
- Better SMTP error handling and testing
- Enhanced email settings view with connection validation

**Documentation:**
- Added `docs/SESSIONHISTORY_2026_CUTOFF.md` - Details on SessionHistory cutoff
- Updated `docs/architecture/CODE_STRUCTURE.md` - Reflected reconciliation focus

**Bug Fixes:**
- Fixed invoice form cancellation type handling
- Improved session alignment verification logic
- Better error handling in reconciliation checker

**Files Changed:**
- Deleted: `app/my_practice/management/commands/recalculate_session_history.py`
- Updated: `verify_session_alignment.py`, `reconciliation_views.py`, `reconciliation_checker.py`
- Updated: `capacity_helpers.py`, `practice_analysis.py`, `email_views.py`
- Updated: Multiple templates for improved UX

## 2026-01-07 - Invoice Editing in App + Date Handling Improvements

**Invoice Editing Feature:**
- New in-app invoice editor at `/invoices/<pk>/edit/`
- No more need to use `/admin/` for invoice editing
- **Features:**
  - Inline editing of all invoice fields and items
  - Add new items dynamically with "➕ Position hinzufügen" button
  - Delete items with visual feedback (striped background)
  - Auto-populate duration and rate based on service type
  - Client-aware rate selection (60/90 min rates)
  - Transaction-safe: All changes saved atomically

**Date Handling Improvements:**
- Fixed invoice_date field to properly handle HTML5 date input format (YYYY-MM-DD)
- Auto-set invoice_date to latest session date when creating/editing draft invoices
- Simplified date field definitions in `InvoiceForm` and `InvoiceItemForm`
- Consistent date handling across create and edit views

**Management Commands:**
- Exclude -G1 and -G2 invoices from `recalculate_totals` and `recalculate_session_history`
- Prevents accidental modification of special invoice types (Gutscheine)

**UI Improvements:**
- Invoice detail page now shows direct link to client detail page
- Edit button on invoice detail page now links to in-app editor instead of admin
- Shared invoice form styles extracted to `includes/invoice_form_styles.html`

**New Files:**
- `app/templates/my_practice/invoice_edit.html` - Edit invoice view
- `app/templates/includes/invoice_form_styles.html` - Shared form styles
- `app/my_practice/management/commands/fix_cancellation_types.py` - Utility command
- `scripts/update_cancellation_items.py` - Update script for cancellation types
- `docs/INVOICE_EDITING.md` - Feature documentation

**Changes:**
- `views/invoice_views.py`: Added `InvoiceEditView` class
- `invoice_forms.py`: Improved date field handling with HTML5 input format
- `urls.py`: Added `/invoices/<pk>/edit/` route
- `invoice_detail.html`: Updated edit button link and added client detail link

## 2026-01-06 - Client Revenue Bug Fix + Centralization

**Critical Bug Fixes:**
- Fixed incorrect revenue calculations in multiple locations
- **Client List view** (`/clients/`): Revenue was multiplied by number of invoice items
- **Practice Analysis**: Revenue-in-period calculations were 2-3× too high
- Problem: Django JOIN multiplication when aggregating over multiple related tables

**Root Cause:**
- Aggregating over `InvoiceItem → invoice__total` multiplies invoice totals by item count
- Multiple annotations over different relations (`invoices` and `invoices__items`) cause JOIN multiplication
- Example: Client PB showed 7840 € instead of correct 2560 €

**Solutions Applied:**
1. **Client List**: Used Subqueries with `OuterRef()` for separate aggregations
2. **Practice Analysis**: Aggregate directly on Invoice table instead of through InvoiceItem
3. **Centralization**: Created reusable methods in `RevenueCalculator`:
   - `get_client_revenue_subquery()` - Safe revenue aggregation
   - `get_client_sessions_subquery()` - Safe session counting

**Files Changed:**
- `views/client_views.py`: Now uses centralized subquery methods
- `utils/practice_analysis.py`: Changed revenue aggregation to Invoice-level
- `utils/revenue_helpers.py`: Added two new centralized subquery methods
- Added prevention guidelines in `docs/BUGFIX_CLIENT_REVENUE_2026-01-06.md`

**Benefits:**
- DRY principle: Subquery logic defined once, used everywhere
- Easier maintenance and testing
- Clear API for future developers

**Testing:**
- All 587 tests passing ✓
- Manual verification confirms consistent calculations across all views

## 2025-12-26 - Client List Improvements & SessionHistory Migration Planning

**Client List Enhancements (`/clients/`):**
- Replaced Email and 90 Min columns with more useful data:
  - **Sessions**: Total session count from paid invoices (excluding cancellations)
  - **Umsatz (Revenue)**: Total revenue from paid invoices
- Both new columns are sortable with NULL values properly sorted to bottom
- Client code now more prominent (larger font, heavier weight, letter-spacing)

**SessionHistory Admin Action:**
- Added "🔗 Link to Client (by client_code)" bulk action
- Automatically links SessionHistory entries to their Client based on client_code
- Shows success/warning messages for linked entries and missing clients

**SessionHistory Migration Plan:**
- Documented complete analysis of SessionHistory usage in TODO.md
- Identified all files needing migration after data reconciliation:
  - `heatmap_utils.py`, `analytics_utils.py`, `practice_analysis.py`, `dashboard_views.py`
- Created 5-step migration plan for post-reconciliation transition

**Bug Fix:**
- Fixed missing `Q` import in `tax_views.py`

## 2025-12-26 - Tax Summary Improvements

**UI/UX Improvements:**
- Improved styling on `/reports/tax-summary/` with better margins and card layout
- Fixed dark-on-dark text issues with proper CSS variable usage
- Months now sorted chronologically (by YYYY-MM key) instead of alphabetically
- Client names marked as `sensitive-data` for privacy

**Tax Focus:**
- Only tax-deductible expenses are now shown (tax-relevant)
- Removed withdrawals section (not relevant for tax reporting)
- Simplified summary calculation: Revenue - Tax-Deductible Expenses = Profit

**Dark Mode Fix:**
- Fixed dark-on-dark text in Client Details table on `/practice-analysis/`
- Added `color: var(--text-primary)` to `.client-table td`

## 2025-12-26 - Dark Mode Fix: Practice Analysis Client Links

**Bug Fix:**
- Fixed dark-on-dark text in "👥 Client Details" table on `/practice-analysis/`
- Added explicit link styling for `.client-table a` using CSS variables
- Links now properly use `var(--link-color)` for dark mode compatibility

**Test Fix:**
- Fixed currency filter tests to match German locale formatting
- Tests now expect comma as decimal separator, period as thousands separator

## 2025-12-26 - Capacity Utilization Chart & Centralized Capacity Helpers

**New Feature: Capacity Trends Chart**
- Added monthly capacity utilization chart to analytics dashboard
- Shows booked hours vs available capacity over time
- Interactive tooltips display detailed capacity metrics

**New Module: capacity_helpers.py**
- Centralized capacity configuration with `CAPACITY_PERIODS`
  - 2020-Jul 2023: 10 hours/week (practice building phase)
  - Aug 2023+: 20 hours/week (full capacity)
- `get_weekly_capacity_for_date()` - Get capacity for any date
- `calculate_period_capacity()` - Full capacity metrics for date range
  - Handles periods spanning multiple capacity configurations
  - Integrates with time-off calculations
- `_get_booked_hours()` - Uses InvoiceItem.duration (preparing for SessionHistory deprecation)

**Refactoring:**
- `practice_analysis.py`: Now uses centralized capacity_helpers
- `analytics_utils.py`: New `get_capacity_trends()` function
- `chart_builder.js`: Added Y-axis labels support with `yAxisSuffix` option

**Bug Fixes:**
- Fixed German locale causing float values to render as "11,0" instead of "11.0"
  - Added `{% load l10n %}` and `|unlocalize` filter in analytics.html
- Fixed JS test imports after chart_utils.js → charts/chart_math.js refactor
- Fixed incorrect test expectation in calculateYearLabels test

**Test Updates:**
- `test_practice_analysis.py`: Updated test data to use InvoiceItems for capacity calculations
- `chart_utils.test.js` & `chart_utils.test.extended.js`: Fixed import paths

## 2025-12-26 - Code Cleanup & Consolidation

**Removed Dead Code:**
- Deleted `view_mixins.py` (166 lines): YearFilterMixin, StatusFilterMixin, SearchMixin, CombinedFilterMixin were never used
- Deleted `dashboard_extras.py`: Single filter (`get_item`) moved to `payment_tags.py`
- Deleted `chart_utils.js` (824 lines): Replaced by modular `charts/` structure
- Deleted `chart_utils_legacy.js`: No longer needed
- Deleted `debug_bk_reconciliation.py`: Redundant debug command
- Deleted `recalculate_invoices.py`: Duplicate of `recalculate_totals.py`
- Deleted `docs/development/TODO.md`: Duplicate of root TODO.md

**Template Tag Consolidation:**
- Merged `get_item` filter from dashboard_extras.py into payment_tags.py
- Updated dashboard.html and heatmap.html to use payment_tags

**Documentation Updates:**
- Removed references to deleted files from CODE_STRUCTURE.md
- Updated README.md: recalculate_invoices → recalculate_totals
- Cleaned up references to old chart_utils.js

**Impact:**
- ~1,200 lines of dead code removed
- Simpler template tag structure (2 files → 1 file for custom filters)
- Management commands reduced from 7 to 5

## 2025-12-26 - Comprehensive Test Suite for Phase 2b Infrastructure

**Test Coverage Added:**
Created comprehensive test suites for all Phase 2b infrastructure (764 lines of production code):
- `test_chart_config.js` (315 lines): 18 test functions covering ChartConfig
  - Color palette and getColor() helper
  - Font configuration and getFont() helper
  - Spacing, padding, grid, tooltip configuration
  - All 4 presets (revenue, expense, comparison, multibar)
  - createGradient() helper
- `test_chart_tooltip.js` (329 lines): 13 test functions covering tooltip system
  - ChartTooltip construction and lifecycle (setup, show, hide, destroy)
  - Custom options and formatters
  - MultiLineTooltip and ComparisonTooltip subclasses
  - Hover detection and positioning
  - DOM management and styling
- `test_chart_builder.js` (441 lines): 17 test functions covering ChartBuilder
  - Fluent API methods (type, data, labels, preset, tooltip, options, colors, datasets)
  - Chart building for all 3 types (bar, line, grouped-bar)
  - Preset integration
  - Validation (missing type, missing data, mismatched lengths)
  - Method chaining and redraw functionality

**Test Infrastructure:**
- Updated test_runner.js to orchestrate all test suites
- Auto-run tests in development mode (DEBUG=True)
- Tests load conditionally via {% if debug %} in analytics.html
- Total test suite: 1,857 lines across 7 files

**Test Metrics:**
- Production code: 764 lines (config + tooltip + builder)
- Test code: 1,085 lines (315 + 329 + 441)
- Test-to-code ratio: 1.42:1 (142% test coverage)
- Total test functions: 48 (18 + 13 + 17)

**Testing Approach:**
- Unit tests for all public methods
- Integration tests for chart building
- Error handling validation
- DOM manipulation verification
- Canvas drawing verification (pixel data checks)

## 2025-12-26 - Models Package Refactoring

**Models Split:**
Split monolithic 731-line models.py into 8 domain-focused modules:
- `models/__init__.py` (27 lines): Package exports with __all__
- `models/practice.py` (148 lines): Practice/practitioner configuration
- `models/client.py` (88 lines): Client management
- `models/service.py` (49 lines): Service type definitions
- `models/invoice.py` (216 lines): Invoice and InvoiceItem models with business logic
- `models/session.py` (67 lines): Session history tracking
- `models/financial.py` (126 lines): CompanyWithdrawal and CompanyExpense
- `models/calendar.py` (45 lines): Google Calendar OAuth2 tokens
- `models/timeoff.py` (65 lines): Holiday and vacation tracking

**Benefits:**
- ✅ No import changes required (all imports from `my_practice.models` still work)
- ✅ Clear domain boundaries (practice, client, invoice, financial, etc.)
- ✅ Easier navigation: Find models by domain instead of scrolling through 731 lines
- ✅ Better IDE support: Auto-complete and go-to-definition work better with smaller files
- ✅ Parallel development: Multiple developers can work on different model domains

**Testing:**
- All 585 tests passing after refactoring
- All 37 model-specific tests passing
- No migration changes required
- Django system check: 0 issues

**Code Metrics:**
- Before: 1 file × 731 lines = 731 lines
- After: 9 files × 831 total lines (includes package structure)
- Average file size: 92 lines per file
- Largest module: invoice.py (216 lines) - contains complex business logic
- Smallest module: calendar.py (45 lines) - single focused model

## 2025-12-26 - Chart Infrastructure Generalization (Phase 1)

**Helper Functions Added:**
- `showChartEmptyState()`: Unified empty data display (eliminated 40+ lines of duplicate code)
- `initializeChart()`: Standardized canvas setup with grid/axes (reduced per-chart boilerplate from 8 to 2 lines)
- `validateChartData()`: Consistent data validation with detailed error reason codes
- `getValidationMessage()`: User-friendly German error messages for validation failures

**Charts Refactored:**
- Revenue Trends: Cleaner initialization and validation
- Expense Trends: Standardized setup and error handling
- Year Comparison: Consistent empty state handling
- Multi-bar Comparison: Unified canvas initialization

**Testing:**
- Added testValidateChartData() with 7 test cases
- Added testGetValidationMessage() with 4 test cases
- All tests passing in browser console

**Code Metrics:**
- Before: 800-line template with duplicate chart code
- After: 720-line template using shared helpers
- Net reduction: 80+ lines of duplicate code eliminated
- Per-chart setup: 8 lines → 2 lines (75% reduction)

## 2025-12-26 - File Splitting & Modularization (Phase 2a)

**JavaScript Module Split:**
- `chart_core.js` (92 lines): Theme system, chart registry, CSS variables
- `chart_helpers.js` (91 lines): Validation, empty state, initialization
- `chart_canvas.js` (94 lines): Canvas setup, grid, axes, Y-axis labels
- `chart_primitives.js` (93 lines): Basic drawing (bars, labels, legend, points)
- `chart_bar.js` (118 lines): Bar chart rendering (simple & grouped)
- `chart_line.js` (131 lines): Line chart rendering, separators, trendlines
- `chart_tooltip.js` (55 lines): Tooltip functionality
- `chart_math.js` (183 lines): Business logic (calculations, parsing, aggregation)

**Test Suite Split:**
- `test_chart_math.js`: Tests for parsing, aggregation, calculations
- `test_chart_helpers.js`: Tests for validation and messages
- `test_runner.js`: Unified test runner

**Template Updates:**
- Updated analytics.html to load modular chart files
- All charts now use focused imports
- Maintained backward compatibility

**Benefits:**
- ✅ Each module 55-183 lines (highly manageable)
- ✅ Clear separation of concerns (theme/render/logic/test)
- ✅ Easy to locate specific functionality
- ✅ Better testability with focused test files
- ✅ Can import only needed functionality
- ✅ Improved git diffs (changes isolated to specific modules)

**Documentation:**
- Created FILE_SPLITTING_PLAN.md with full Phase 2/3 roadmap
- Documents next steps: tooltip system, config, builder pattern

## 2025-12-26 - Phase 2b: Advanced Chart Features

**New Modules Added:**

1. **chart_config.js** (232 lines) - Centralized Configuration
   - Color palettes (primary, secondary, success, warning, danger, neutral)
   - Typography settings (fonts for axis, labels, values, tooltips)
   - Spacing configuration (padding, bar spacing, line widths)
   - Grid and tooltip settings
   - Chart-specific presets (revenue, expense, comparison, multibar)
   - Helper methods: getColor(), getPreset(), getPadding(), getFont(), createGradient()
   - CSS variable fallback support for dark mode

2. **chart_tooltip_enhanced.js** (216 lines) - Generic Tooltip System
   - `ChartTooltip` class with configurable formatting and styling
   - `MultiLineTooltip` class for rich multi-line tooltips
   - `ComparisonTooltip` class for grouped bar charts
   - Automatic hover detection with configurable radius
   - Custom formatter support
   - Smooth transitions and positioning
   - Proper cleanup and event handler management

3. **chart_builder.js** (316 lines) - Fluent Chart Builder API
   - Fluent API for minimal boilerplate
   - Automatic validation and error handling
   - Preset integration (revenue, expense, comparison presets)
   - Built-in tooltip support
   - Support for bar, line, and grouped-bar charts
   - Custom color overrides
   - Auto-configuration from presets

**Example - Expense Trends Chart Refactored:**

Before (38 lines):
```javascript
// Validate data
const validation = validateChartData(data, { checkNonZero: true });
if (!validation.valid) {
    showChartEmptyState(canvas, getValidationMessage(validation.reason));
    return;
}

// Initialize chart
const setup = initializeChart(canvas, { padding: {...} });
if (!setup) return;
const { ctx, padding, chartWidth, chartHeight, height } = setup;

// Draw elements
drawYAxisLabels(ctx, padding, chartHeight, validation.maxValue);
const barPositions = drawSimpleBarChart(...);
setupTooltip(canvas, barPositions, data, years);
```

After (8 lines - 79% reduction!):
```javascript
new ChartBuilder(canvas)
    .type('bar')
    .data(data)
    .labels(years)
    .preset('expense')
    .tooltip((d) => `<strong>${d.label}</strong><br>${Math.round(d.value)} €`)
    .build();
```

**Benefits:**
- ✅ 79% reduction in chart setup code (38 → 8 lines)
- ✅ Consistent styling via centralized config
- ✅ Easy theme changes (modify config, all charts update)
- ✅ Dark mode support via CSS variables
- ✅ Reusable tooltip system across all charts
- ✅ Type-safe builder pattern with fluent API
- ✅ Automatic validation, error handling, empty states
- ✅ Preset system for common chart types

**Code Metrics:**
- Added 764 lines of reusable infrastructure
- Reduced template code by 30 lines (776 → 746 lines)
- Expense Trends chart: 38 → 8 lines (79% reduction)
- Future charts can be created in 5-10 lines

**Next Steps (Phase 3 - Optional):**
- Refactor remaining 3 charts to use ChartBuilder
- Add animation system
- Export to PNG/SVG
- Chart responsive sizing
- More chart types (pie, scatter, etc.)

## 2025-12-26 - Phase 2c: Refactor All Charts with Builder Pattern

**Charts Refactored to ChartBuilder:**

1. **Expense Trends Chart**
   - Before: 38 lines of setup code
   - After: 8 lines with ChartBuilder
   - Reduction: 79% (30 lines saved)

2. **Revenue Trends Chart**
   - Before: 95 lines of complex rendering code
   - After: 12 lines with ChartBuilder
   - Reduction: 87% (83 lines saved)

3. **Multi-bar Comparison Chart**
   - Before: 99 lines with manual hover detection
   - After: 16 lines with ChartBuilder
   - Reduction: 84% (83 lines saved)

**Total Impact:**
- Template: 776 → 572 lines (204 lines / 26% reduction)
- Code removed: 175 lines of duplicate boilerplate
- Code added: 29 lines of declarative builder calls
- Net savings: 146 lines eliminated
- Average reduction per chart: 83%

**Year Comparison Chart:**
- Not refactored (uses custom zero-line logic for +/- profit display)
- Could be refactored with custom rendering extension in future

**Before vs After Example:**

```javascript
// BEFORE (Expense Trends - 38 lines):
const validation = validateChartData(data, { checkNonZero: true });
if (!validation.valid) {
    showChartEmptyState(canvas, getValidationMessage(validation.reason));
    return;
}
const setup = initializeChart(canvas, { padding: {...} });
if (!setup) return;
const { ctx, padding, chartWidth, chartHeight, height } = setup;
drawYAxisLabels(ctx, padding, chartHeight, validation.maxValue);
const barPositions = drawSimpleBarChart(ctx, padding, chartWidth,
    chartHeight, height, years, data, validation.maxValue, '#ed8936', {
        showValueLabels: false
    });
setupTooltip(canvas, barPositions || [], data, years);

// AFTER (Expense Trends - 8 lines):
new ChartBuilder(canvas)
    .type('bar')
    .data(data)
    .labels(years)
    .preset('expense')
    .tooltip((d) => `<strong>${d.label}</strong><br>${Math.round(d.value)} €`)
    .build();
```

**Benefits Realized:**
- ✅ Consistent API across all charts
- ✅ Automatic validation and error handling
- ✅ Standardized tooltips with rich formatting
- ✅ Theme integration (colors from presets)
- ✅ Dark mode support via CSS variables
- ✅ Dramatically reduced template complexity
- ✅ Easier to add new charts (5-15 lines each)
- ✅ Single source of truth for chart styling

**Code Metrics Summary:**
- Phase 1: 800 → 720 lines (10% reduction, helper functions)
- Phase 2a: 823 → 8 modules (modularization)
- Phase 2b: +764 lines (config, tooltip, builder infrastructure)
- Phase 2c: 776 → 572 lines (26% reduction in template)
- **Total template reduction: 800 → 572 lines (28% overall)**

**Next Steps (Phase 3 - Optional):**
- Refactor remaining 3 charts to use ChartBuilder
- Add animation system
- Export to PNG/SVG
- Chart responsive sizing
- More chart types (pie, scatter, etc.)

## 2025-12-26 - Chart Infrastructure Generalization

**Helper Functions Added:**
- `showChartEmptyState()`: Unified empty data display (eliminated 40+ lines of duplicate code)
- `initializeChart()`: Standardized canvas setup with grid/axes (reduced per-chart boilerplate from 8 to 2 lines)
- `validateChartData()`: Consistent data validation with detailed error reason codes
- `getValidationMessage()`: User-friendly German error messages for validation failures

**Charts Refactored:**
- Revenue Trends: Cleaner initialization and validation
- Expense Trends: Standardized setup and error handling
- Year Comparison: Consistent empty state handling
- Multi-bar Comparison: Unified canvas initialization

**Testing:**
- Added testValidateChartData() with 7 test cases
- Added testGetValidationMessage() with 4 test cases
- All tests passing in browser console

**Code Metrics:**
- Before: 800-line template with duplicate chart code
- After: 720-line template using shared helpers
- Net reduction: 80+ lines of duplicate code eliminated
- Per-chart setup: 8 lines → 2 lines (75% reduction)

## 2025-12-26 - File Splitting & Modularization (Phase 2a)

**JavaScript Module Split:**
- `chart_core.js` (92 lines): Theme system, chart registry, CSS variables
- `chart_helpers.js` (91 lines): Validation, empty state, initialization
- `chart_canvas.js` (94 lines): Canvas setup, grid, axes, Y-axis labels
- `chart_primitives.js` (93 lines): Basic drawing (bars, labels, legend, points)
- `chart_bar.js` (118 lines): Bar chart rendering (simple & grouped)
- `chart_line.js` (131 lines): Line chart rendering, separators, trendlines
- `chart_tooltip.js` (55 lines): Tooltip functionality
- `chart_math.js` (183 lines): Business logic (calculations, parsing, aggregation)

**Test Suite Split:**
- `test_chart_math.js`: Tests for parsing, aggregation, calculations
- `test_chart_helpers.js`: Tests for validation and messages
- `test_runner.js`: Unified test runner

**Template Updates:**
- Updated analytics.html to load modular chart files
- All charts now use focused imports
- Maintained backward compatibility

**Benefits:**
- ✅ Each module 55-183 lines (highly manageable)
- ✅ Clear separation of concerns (theme/render/logic/test)
- ✅ Easy to locate specific functionality
- ✅ Better testability with focused test files
- ✅ Can import only needed functionality
- ✅ Improved git diffs (changes isolated to specific modules)

**Documentation:**
- Created FILE_SPLITTING_PLAN.md with full Phase 2/3 roadmap
- Documents next steps: tooltip system, config, builder pattern

## 2025-12-26 - Chart Infrastructure Generalization

### Chart Helper Functions (Phase 1 Complete)
- **Standardized Chart Utilities**: Created reusable helper functions for all charts
  - `showChartEmptyState()`: Unified empty data display across all charts
  - `initializeChart()`: Standardized canvas setup with grid/axes (8 lines → 2 lines per chart)
  - `validateChartData()`: Consistent data validation with detailed error reasons
  - `getValidationMessage()`: User-friendly error messages for validation failures
  - Eliminated 40+ lines of duplicate code across 4 chart types

- **Refactored All Charts**: Applied helpers to complete analytics dashboard
  - Revenue Trends (line chart): Cleaner initialization and validation
  - Expense Trends (bar chart): Standardized setup and error handling
  - Year Comparison (profit/loss bars): Consistent empty state handling
  - Multi-bar Comparison: Unified canvas initialization

- **Enhanced Test Coverage**: Extended JavaScript test suite
  - Added `testValidateChartData()` with 7 test cases
  - Added `testGetValidationMessage()` with 4 test cases
  - Total: 26 automated tests for chart utilities
  - All tests passing in browser console with `runAllChartTests()`

- **Code Metrics**:
  - Before: ~800 lines template + ~700 lines utils = 1500 total
  - After: ~720 lines template + ~777 lines utils = 1497 total
  - Net reduction: 40+ lines of duplicates eliminated
  - Improved: Consistency, maintainability, testability

## 2025-12-25 - Code Harmonization & Bug Fixes

### Bug Fix: Expense Chart Distribution
- **Fixed Empty Expense Trends**: Corrected expense data distribution in analytics dashboard
  - Root cause: Refactored `ExpenseAnalyzer.get_monthly_trends()` incorrectly filtered by month
  - All expenses are dated 31.12. of each year, must filter by year only
  - Now distributes yearly totals equally across 12 months for proper chart visualization
  - Added comprehensive test `test_analytics_expense_trends_december_31_distribution` to prevent regression
  - Expense trends chart now displays correctly with proper monthly distribution

### Date Formatting Standardization
- **Centralized Date Helpers**: Unified all date formatting through `format_month_key()` and `format_month_label()`
  - Replaced 8 instances of direct `strftime()` calls across codebase
  - Updated files: `analytics_utils.py`, `dashboard_views.py`, `tax_views.py`, `reconciliation.py`
  - Consistent formatting: "YYYY-MM" for keys, configurable labels (short/medium/long)
  - Improved maintainability and reduced code duplication

### Analytics Refactoring
- **Generic Monthly Aggregation**: Created reusable `_get_monthly_aggregation()` helper
  - Extracted common pattern from `RevenueAnalyzer` and `ExpenseAnalyzer`
  - Reduced ~64 lines of duplicated code
  - Simplified both `get_monthly_trends()` methods from ~40 to ~18 lines each
  - More maintainable and extensible for future analyzers

### Test Coverage Improvements
- **New Test Suite**: `test_chart_helpers.py` with 21 comprehensive tests
  - 3 tests for `format_month_key()` (various date formats)
  - 5 tests for `format_month_label()` (short/medium/long formats)
  - 5 tests for `aggregate_invoice_items_by_month()` (cancellations, quantities, edge cases)
  - 8 tests for `prepare_monthly_chart_data()` (sorting, formats, empty data)
- **Updated Tests**: Fixed 2 existing tests in `test_analytics_utils.py` for new date format
- **Total**: 28 tests passing (7 analytics + 21 chart helpers)

### Code Quality
- **Import Optimization**: Moved `Count` import to module level in `analytics_utils.py`
- **Minor Fixes**:
  - Removed extra blank line in `client_views.py`
  - Improved dormant client toggle function in `practice_analysis.html`

## 2025-12-24 - CSS Architecture Consolidation & Testing Improvements

### CSS Architecture Overhaul
- **Modular CSS System**: Extracted ~1300+ lines of inline/embedded styles from templates
  - Created dedicated CSS files for page-specific styles
  - `expenses.css` (~250 lines): Expense list and management pages
  - `practice_analysis.css` (~300 lines): Practice capacity analysis
  - `reconciliation.css` (~90 lines): Data reconciliation views
  - `imports.css` (~95 lines): Import pages shared components
  - `tax_summary.css` (~150 lines): Tax year summary page
  - `calendar_import.css` (~50 lines): Calendar import functionality

### Common Component Library
- **Badge Component**: Centralized badge system in `common.css`
  - Base `.badge` with standard variants: success, danger, warning, info
  - Page-specific badge extensions remain in dedicated CSS files
- **Card Component**: Generic `.card` base class for consistent card styling
  - `.import-card` and `.analytics-card` extend from base
  - Reduces duplication across ~50+ card instances
- **Action Buttons**: `.action-buttons` utility for button groups
- **Stat Card Variants**: All gradient variants (success, warning, primary, secondary, neutral) in common.css

### CSS Deduplication
- **analytics.css**: Reduced from 378 to ~320 lines (-22% duplication)
- **common.css**: Expanded with reusable components (badges, cards, action-buttons)
- **Template Cleanup**: Removed embedded `<style>` blocks from 9+ templates
  - `expense_list.html`: 265→0 lines (fully extracted)
  - `practice_analysis.html`: 187→1 line (one dynamic inline style)
  - `reconciliation.html`: ~150 lines extracted, complex modals kept
  - `calendar_import.html`, `tax_year_summary.html`, `import_base.html`: fully cleaned

### Testing Infrastructure
- **Test Runner Optimization** (`dev.py`):
  - JavaScript tests now skipped when specific Django test modules are provided
  - Speeds up development workflow when testing specific functionality
- **Logger Cleanup**:
  - Fixed noisy email test logs (corrected logger name from `my_practice.views.email_views` to `my_practice.email`)
  - Tests now run with minimal console output
- **Bug Fixes**:
  - Fixed `test_expense_views.py`: Removed invalid 'practice' field, corrected category values
  - Fixed `test_email_views.py`: Corrected POST parameter from 'quick' to 'quick_send'
  - Fixed `expense_list.html` template syntax error (orphaned CSS code after refactoring)

### UI Improvements
- **Analytics Top Clients Table**: Added proper table styling with hover effects and readable text colors
- **Invoice Search Results**: Improved visibility with primary text color and highlighted counts
- **Dark Mode Compatibility**: All new CSS uses CSS variables for theme support

### Technical Debt Reduction
- **Total Lines Reduced**: ~1300+ lines of duplicate/embedded CSS eliminated
- **Maintainability**: Centralized styling makes updates easier and more consistent
- **Performance**: Reduced HTML payload, better browser caching with separate CSS files

## 2025-12-24 - Practice Analysis & Capacity Planning

### Practice Analysis Feature
- **New Analysis View**: Comprehensive practice management overview at `/practice-analysis/`
  - Period-based analysis: Month, Quarter, Half-Year, Year, Custom Range
  - Client classification: Probatoric (<5 sessions), Active, Established, Dormant
  - Capacity metrics: Working days, available hours, utilization percentage
  - Time off integration with capacity impact calculation
  - Online/In-person client tracking

### Smart Insights Generation
- **Automated insights** generated for each period:
  - Period overview (days analyzed, active client ratio)
  - Client concentration warnings (top 3 clients dominating)
  - Average sessions per active client
  - Capacity utilization assessment (low/moderate/good/high)
  - Probatoric client growth potential
  - Dormant client alerts (>5 dormant)
  - Revenue opportunities (sessions without invoices)

### Historical Trends
- **4-Quarter Trend Analysis**: Automatic calculation of last 4 quarters
  - Capacity percentage trends over time
  - Active client count evolution
  - Total sessions per quarter
  - Time off impact per period
  - Helps identify seasonal patterns and growth trajectory

### New Utilities
- **`practice_analysis.py`**: PracticeAnalyzer class with comprehensive analysis engine
  - Client classification logic
  - Capacity calculation (working days, available hours, utilization)
  - Time off integration via `calculate_timeoff_for_period()`
  - Insight generation algorithm
  - `calculate_quarter_trends()` function for historical analysis
- **TimeOff Enhancements**: Period-based calculations now work for arbitrary date ranges

### UI Features
- **Period Selector**: Interactive buttons for quick period switching
- **Custom Range Toggle**: Date picker for flexible analysis periods
- **Dormant Client Filter**: JavaScript toggle to show/hide dormant clients
- **Client Table**: Code, Name (sensitive), Status badges, Sessions, Type, Invoices
- **Trends Table**: 4-quarter comparison with key metrics
- **Responsive Design**: Dark mode support with proper CSS variables

### Bug Fixes
- Fixed TimeOff card showing incorrect weeks (data entry: 2026-09-04 → 2026-01-05)
- Fixed Reconciliation tests (clients without invoices now properly flagged)
- Fixed Dashboard grid wrapping (2-column layout on medium screens)
- Fixed Analytics TimeOff display (period-based instead of full year)
- Fixed dark mode text visibility issues across multiple templates

### Tests
- **34 TimeOff tests**: 24 existing + 10 new period-based tests
- **30 Reconciliation tests**: All passing after logic fixes
- All practice analysis calculations validated

## 2025-12-23 - Analytics Time Filter & Test Infrastructure

### Analytics Time Period Filter
- **Time Filter UI**: Added period selector to analytics dashboard
  - Filter options: All Time, Last Month, Last Quarter, Last Year, Custom Range
  - Date range picker for custom periods
  - Filter persistence in URL parameters
  - Reset button when filter is active
- **Backend Filtering**: Updated analytics_utils.py functions to support date ranges
  - `get_revenue_trends()`, `get_monthly_expenses()` now accept `start_date` parameter
  - `get_revenue_vs_withdrawals()`, `calculate_profit()` filter by date ranges within years
  - Fixes to `RevenueAnalyzer`, `ExpenseAnalyzer`, `ProfitCalculator` classes
- **Interactive Charts**: Added hover tooltips to comparison chart
  - Shows year, category (Umsatz/Ausgaben/Entnahmen), and exact value
  - Smooth cursor tracking with pointer indication
- **9 comprehensive tests** in test_analytics_time_filter.py

### Critical Bug Fix: get_year_from_request
- **Issue**: Function was returning current year (2025) as default even when `default=None` was passed
- **Impact**: All views with year filtering were incorrectly filtering to 2025, causing test failures
- **Fix**: Changed function to return `default` directly instead of fallback to `datetime.now().year`
- **Result**: All expense, withdrawal, and tax list views now correctly show all data when no year filter is set

### View Test Infrastructure Improvements
- **50 new view tests** created/updated:
  - `test_views_expense.py` - 13 tests for expense CRUD operations
  - `test_views_withdrawal.py` - 20 tests for withdrawal management
  - `test_views_tax.py` - 15 tests for tax year summary
  - `test_analytics_time_filter.py` - 9 tests for analytics filtering
- **Test Robustness**: Changed from template text assertions to context data checks
  - Tests now check `response.context['total_revenue']` instead of searching for "300,00" in HTML
  - More reliable and independent of template rendering details
- **Total: 363 tests** passing (all Django + JavaScript tests)

## 2025-12-23 - CRUD Mixins & View Test Coverage

### CRUD Mixins (Phase 9)
- **Generic CRUD Mixins**: Created `views/crud_mixins.py` with 3 reusable mixins (137 lines):
  - `FormCreateViewMixin` - Generic create handling with form validation and messages
  - `FormUpdateViewMixin` - Generic update handling with instance management
  - `FormDeleteViewMixin` - Generic delete handling with confirmation
- **Refactored Views**:
  - `expense_views.py` - Using mixins (112 lines, was 110)
  - `withdrawal_views.py` - Using mixins (97 lines, was 99)
- **~60 lines of duplicate CRUD code eliminated**
- **Reusable for future models** (Client, ServiceType, etc.)

### View Test Coverage (Phase 8)
- **68 new view tests** created across 3 files:
  - `test_views_analytics.py` - 11 tests for analytics dashboard
  - `test_views_reconciliation.py` - 11 tests for API endpoints
  - `test_views_client.py` - 10 tests for client views (7 active)
- **Fixed existing view tests**: test_views_dashboard.py, test_views_invoice.py, test_views_invoice_simple.py
- **Total: 299 tests** passing (68 view + 231 utility)
- **Regression protection** for future refactoring

### Performance & Code Quality
- Fixed linting errors (F821, E402, unreachable code)
- Updated IMPROVEMENTS.md with Phases 7-9
- All tests passing with no errors

## 2025-12-23 - Deduplication & Expense CRUD

### Component Deduplication
- **Pagination Component**: Created reusable `includes/pagination.html` with `query_string` template tag
- **Empty State Component**: Added `includes/empty_state.html` for consistent "no data" messages
- **Aggregation Helpers**: New `utils/aggregation_helpers.py` with 6 reusable functions:
  - `get_yearly_totals()` - Year-based aggregation
  - `get_category_breakdown()` - Category breakdown with human-readable names
  - `get_monthly_breakdown()` - Month-based aggregation
  - `get_grand_total()` - Grand total with optional filtering
  - `get_year_over_year_comparison()` - YoY comparison with growth
  - `YearFilterMixin` - Automatic year filtering
  - `StatusFilterMixin` - Status filtering
  - `SearchMixin` - Multi-field search
  - `CombinedFilterMixin` - All three combined

### View Refactoring
- **expense_views.py**: Refactored to use aggregation helpers, added CRUD operations
- **withdrawal_views.py**: Refactored to use aggregation helpers
- **tax_views.py**: Refactored to use aggregation helpers
- **~40 lines** of duplicate aggregation code eliminated

### Expense Management
- **CRUD Operations**: Full create/update/delete for company expenses
- **Year Filtering**: Clickable year cards filter expenses by year
- **Forms**: Added `CompanyExpenseForm` with all fields and validation
- **Templates**: Created expense_form.html and expense_confirm_delete.html

### CSS Components
- **Filter Bar Components**: Added `.filter-bar`, `.filter-btn`, `.filter-select` classes
- **Active State Styling**: Hover effects and active states for filter buttons
- **Dark Mode Compatible**: All new components support dark mode

### Testing
- **10 new tests** for aggregation helpers in test_aggregation_helpers.py
- **6 new tests** for query_string template tag in test_template_tags.py
- **Total: 189 tests** passing

### Documentation
- Updated CODE_STRUCTURE.md, CENTRALIZATION_OPPORTUNITIES.md, IMPROVEMENTS.md
- All new components documented with usage examples

### Cleanup
- Deleted obsolete `run_tests.sh` script

## 2025-12-22 - Session Counting Centralization

### Core Refactoring
- **Centralized Calculation Functions**: New `count_sessions()` and `count_sessions_rounded()` in utils/calculations.py
- **Formula Standardization**: `(duration / 60.0) * quantity` applied consistently across entire application
- **Reconciliation Utilities**: Extracted all reconciliation logic into testable utils/reconciliation.py module
- **Management Commands**: Added recalculate_session_history, verify_session_alignment, and debug_bk_reconciliation

### Analytics Integration
- **Heatmap**: Updated _get_sessions_from_invoices() to use centralized counting with proper grouping
- **Busiest Months**: SessionAnalyzer.get_busiest_months() now handles quantity multiplication correctly
- **Top Clients**: ClientAnalyzer.get_top_by_revenue() uses accurate session hour calculations

### Data Migration
- **SessionHistory Recalculation**: 254 months updated, 62 new entries created
- **Alignment Verification**: 579/778 months (74.4%) perfect match, 197 missing historical invoices identified
- **Float Comparison**: Added 0.01 tolerance for precision handling

### Testing & Documentation
- **58 Comprehensive Tests**: test_calculations.py (27), test_reconciliation.py (19), test_analytics_integration.py (12)
- **Detailed Documentation**: SESSION_COUNTING_REFACTOR.md with migration notes and usage examples
- **Invoice Archaeology Tool**: scripts/invoice_archaeology.py for PDF text extraction

### UI Improvements
- **Reconciliation View**: Now shows both calculation errors and missing invoices as discrepancies
- **Inline Editing**: Enhanced with proper service type support and AJAX updates

## 2025-12-21 - Performance Optimizations Phase 2

### Database Optimization
- **Migration 0014**: Added `InvoiceItem.session_date` index for 50-60% faster date-range queries
- **All model Meta classes**: Added index definitions for consistency and maintainability

### N+1 Query Elimination
- **reconciliation_overview**: 94% query reduction (50→3 queries) using prefetch_related
- **client_detail**: 73% query reduction (15→4 queries) with prefetch + DB aggregation
- **Top Clients analyzer**: 90-95% faster with single annotated query instead of per-client loops

### Code Deduplication
- **heatmap_utils.py**: Extracted unified `get_sessions_for_month()` helper function
- **Centralized constants**: SESSION_HISTORY_CUTOFF for session data source switching
- **40 lines removed**: DRY principle applied to duplicate session retrieval logic

### Database Aggregation
- **Invoice.calculate_total()**: 20-30% faster using DB-level Sum() instead of Python loops

### Template & Validation Fixes
- **Fixed duplicate `{% block extra_css %}` in client_detail.html**: Removed nested block that caused template rendering error
- **Added `{% load payment_tags %}` to client_detail.html**: Fixed missing currency filter by loading custom template tags
- **Invoice validation skip for management commands**: Added optional `skip_validation` parameter to Invoice.save() method to prevent validation errors when recalculating totals on historical data with invalid dates
- **Dark mode CSS improvements**: Unified h1-h6 element styling for consistent theme transitions

## 2025 - Foundation

### Core System Setup
- **Django + PostgreSQL + Docker**: Complete containerized development environment
- **Data Models**: Client, Invoice, InvoiceItem, ServiceType, Practice
- **Invoice Management**: Auto-numbering (CLIENT-1, CLIENT-2), manual override possible
- **Bilingual PDFs**: DE/EN templates with WeasyPrint, professional layout, tax compliance (§19 UStG)
- **Admin Interface**: Django admin with image previews, inline editing

### UI/UX Fundamentals
- **Privacy Mode**: Blur sensitive data (names, emails, addresses) with localStorage toggle
- **Dark Mode**: System-wide dark theme with CSS variables
- **Status Workflow**: Draft → Sent → Paid with automatic paid_date tracking
- **Quick Status Changes**: AJAX dropdown for instant status updates

### Data Import System
- **CSV Import Framework**: Multi-format support (2020-2024 invoice formats)
- **Auto-create Clients**: Missing clients created automatically during import
- **German Decimal Parsing**: Handles 1.234,56 and 1,234.56 formats
- **Session History Import**: Historical session data from external sources

## December 2025 - Analytics & Financial Tracking

### Analytics Dashboard (Early Dec)
- **Revenue Trends**: 72-month line chart with interactive tooltips (2020-2025)
- **Year-over-Year Comparison**: Bar chart with 6 colored bars, growth indicators
- **Top Clients**: Top 10 by revenue with clickable links to detail pages
- **Client Detail Pages**: Individual client pages with invoice history, revenue timeline charts
- **Activity Heatmap**: Historical + current sessions, time navigation, warm color palette
- **Session Type Distribution**: Breakdown of 60min, 90min, group sessions

### Code Quality Improvements (Mid Dec)
- **Views Modularization**: Split 1480-line views.py into 7 focused modules
  - client_views.py, invoice_views.py, dashboard_views.py, api_views.py, analytics_views.py, import_views.py
- **CSS Deduplification**: Extracted common.css (420 lines), analytics.css (206 lines)
- **Template Refactoring**: Created import_base.html, saved ~520 lines (-58%)
- **Import Helpers**: BaseImportHelper class for DRY CSV processing
- **Documentation**: CODE_STRUCTURE.md, REFACTORING.md

### Financial Tracking System (Mid Dec)
- **Company Withdrawals**: Track personal money withdrawn (24 entries, ~€70k, 2023-2025)
  - Categories: Personal salary, Tax payment, Other
  - CSV import support
  - Analytics integration with trends chart
- **Business Expenses**: Track operating expenses (148 entries, ~€50k, 2019-2025)
  - 17 categories: Miete, Software, Versicherung, Supervision, Training, etc.
  - Tax deductible tracking
  - CSV import with year parameter
  - Category breakdown charts
- **True Net Profit**: Revenue - Expenses - Withdrawals
  - 6-year comparison cards
  - Expense trends chart (72 months, orange/red gradient)
  - Category distribution visualization

### Navigation Enhancement (Dec 18)
- **Financial Dropdown Menu**: "💰 Finanzen" with Entnahmen, Ausgaben
- **Extended Import Menu**: 4 options (Rechnungen, Sitzungshistorie, Entnahmen, Ausgaben)
- **Improved JavaScript**: Multiple dropdown support, 200ms hover delay

### Email Integration (Dec 18)
- **Proton Bridge SMTP**: Full integration with localhost:1025
- **Custom ProtonBridgeEmailBackend**: Handles self-signed certificates
- **Two Send Modes**:
  - Quick Send ("Send!"): One-click with default template + confirmation
  - Custom Send ("Send..."): Editable subject and body in form
- **Custom Salutations**: Per-client personal greetings (Dear X / Liebe:r X)
- **Bilingual Email Templates**: DE/EN with placeholders ({salutation}, {invoice_number}, {amount}, {date}, {client_name})
- **Auto Status Update**: Invoice status → "sent" on successful delivery
- **Re-send Protection**: Prevents duplicate sends for already-sent invoices
- **Comprehensive Logging**: Full email lifecycle logged for debugging
- **Salutation Warnings**: UI hints when client has no custom salutation set
- **Imported Client Detection**: Warnings for placeholder data (Klient XX, xx@example.com)
- **Development Tool**: `./dev.py restart --force` for .env variable reload
- **See**: [EMAIL_IMPLEMENTATION.md](EMAIL_IMPLEMENTATION.md) for full details

### Financial Accuracy Fix (Dec 18)
- **Profit Calculation Standardization**: Dashboard now matches Analytics
  - Changed from `invoice_date` filtering to `paid_date` with fallback
  - Tax-accurate: Revenue counted when payment received, not when invoice issued
  - Resolves €1,689 discrepancy between Dashboard (28,471€) and Analytics (30,160.50€)
  - Both views now use identical logic: `Q(paid_date__year=year) | Q(paid_date__isnull=True, invoice_date__year=year)`

### UI Polish (Dec 18)
- **Dark Mode Fixes**: 50+ dark-on-dark text issues resolved
- **German Currency Format**: "2680 €" with &nbsp; (19 occurrences)
- **Table Unification**: .data-table component with sortable headers
- **Client List Filters**: Clickable stat cards (All, Active, DE, EN)
- **Client Edit Form**: Combined create/update view, active/inactive checkbox
- **Session Count Simplification**: Removed confusing hour calculations until data reconciliation

### Phase 5: Advanced Features & Quality (Dec 21, 2025)

**Analytics Refactoring**
- **Analyzer Classes**: Refactored analytics_utils.py into 5 logical classes
  - RevenueAnalyzer: Monthly trends, yearly comparison, revenue calculations
  - SessionAnalyzer: Session type distribution and counting
  - ClientAnalyzer: Top clients by revenue, client rankings
  - ExpenseAnalyzer: Monthly trends, category breakdowns
  - ProfitCalculator: Yearly profit with cumulative tracking
  - Backward compatible wrapper functions maintained
  - 7 comprehensive unit tests added (test_analytics_utils.py)

**Tax Year Summary**
- **Steuererklärung View**: Comprehensive annual tax report
  - Monthly revenue breakdown with invoice details
  - Expense categories with percentages and tax deductibility
  - Withdrawal tracking by category
  - Profit calculations (gross and net)
  - Print-friendly layout with collapsible sections
  - Year selector dropdown
  - Dark mode compatible with CSS variables

**Import System Enhancement**
- **BaseCSVImporter Pattern**: Refactored import views for DRY principles
  - ExpenseImporter and WithdrawalImporter now use base class
  - ~155 lines of code duplication eliminated
  - Cleaner separation of parsing and business logic
  - Consistent error handling and user feedback
  - session_history.py kept as-is (pivot table format requires special handling)
  - invoices.py kept as-is (complex specialized logic with 10+ business rules)

**Validation & Data Quality**
- **Invoice Duplicate Prevention**: Model-level validation with clean() method
  - Prevents duplicate invoice numbers within same client
  - User-friendly German error messages
  - 6 unit tests for validation logic (test_invoice_validation.py)

**Template Filters**
- **Percentage Filter**: New template filter for tax summary
  - Handles zero division gracefully
  - None/null value safety
  - 6 comprehensive tests

**Bug Fixes**
- Fixed dark mode support in tax summary (CSS variables instead of fixed colors)
- Fixed WithdrawalImporter AttributeError (missing handle() method)
- Fixed template TemplateSyntaxError (missing payment_tags load in import templates)

## Data Status (Dec 2025)

### Imported Historical Data
- **Invoices**: Complete 2020-2025
- **Session History**: Complete through 2025
- **Withdrawals**: 24 entries (2023-2025)
- **Expenses**: 148 entries (2019-2025)

### Next Milestone
- **January 2026**: Final CSV upload before full Django-native workflow

## Technical Highlights

### Performance
- **PDF Optimization**: Image compression 500KB → 27KB (95% reduction)
- **Template Caching**: Disabled in DEBUG mode for development speed
- **WhiteNoise**: Static file serving without collectstatic in development

### Developer Experience
- **Conditional STORAGES**: Simple in DEBUG, compressed/manifest in production
- **Remainder Distribution**: Exact cent-accurate invoice calculations
- **German Locale**: Full German UI (PDFs remain bilingual)
- **Gunicorn**: 1 worker for consistent reload behavior

## Documentation

- **README.md**: Setup, Docker, Proton Bridge, Backup/Restore
- **CODE_STRUCTURE.md**: Architecture, modules, utilities (304 lines)
- **REFACTORING.md**: CSS/Template refactoring history (258 lines)
- **EMAIL_IMPLEMENTATION.md**: Email feature implementation details (187 lines)
- **TODO.md**: Current tasks, known issues, future features
- **This file**: Chronological feature history

## Statistics (Dec 18, 2025)

### Code Metrics
- **Python**: ~8,000 lines (modularized into 7 view modules + utils)
- **Templates**: ~3,500 lines (deduplicated, shared components)
- **CSS**: ~1,800 lines (common.css, analytics.css, per-page styles)

### Refactoring Savings
- Import templates: -520 lines (-58%)
- Views modularization: Better organization, easier maintenance
- CSS deduplication: ~200 lines removed total

### Feature Count
- **Models**: 7 (Client, Invoice, InvoiceItem, ServiceType, Practice, CompanyWithdrawal, CompanyExpense, SessionHistory)
- **Views**: 20+ (dashboard, analytics, clients, invoices, imports, emails)
- **CSV Imports**: 4 types (invoices, sessions, withdrawals, expenses)
- **Charts**: 8+ (revenue trends, YoY comparison, expense trends, client timelines, heatmap)
