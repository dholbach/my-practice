# TODO - Payments System

Open backlog only. For completed work history: [docs/CHANGELOG.md](docs/CHANGELOG.md).

---

## Named Projects (Multi-Session)

| ID | Titel | Aufwand | Details |
| --- | --- | --- | --- |
| P-029 | Import Old Session Logs | ~4h | Management command `import_session_logs`, CSV + Fernet |
| P-023 | SMS-Versand (seven.io) | ~4h | Absagen + Schnell-SMS; AVV zuerst → [P-023](docs/projects/todo/P-023_SMS_CANCELLATION.md) |

---

## Enhancements & Kleinaufgaben

### OSS / Self-hosting (post P-024)

- [ ] Extend CI beyond lint: run pytest suite
- [ ] OSS governance: GitHub Discussions + responsible-disclosure policy

### Backup

- [ ] **Backup verification** — Restore-Smoketest auf Testumgebung (regelmäßig per Checklist)

### Test Coverage (66% overall — 2026-04-28; 937 tests as of 2026-06-09)

Critical gaps (0–20%):

- [ ] `calendar_views.py` 10%, `contract_form.py` 15% — highest-value targets remaining
- [ ] Management commands at 0%: `fetch_calendar_events`, `prune_old_backups`
- [ ] `calendar_event_processor.py` 23%, `calendar_preflight.py` 19% — new production code from P-100 with no tests yet; highest-value targets in utils
- [ ] `email_backend.py` 0%, `csv_parser.py` 0%

Medium gaps (30–55%):

- [ ] `email_views.py` 41%, `api_views.py` 42%, `invoice_views.py` 44%
- [ ] `practice_helpers.py` 31%, `import_helpers.py` 33%, `client_helpers.py` 37%

---

## CSS Dedup Backlog (medium effort)

Identified during P-045 follow-up (2026-06-18). No template changes needed unless noted.

- [ ] **Left-accent box family** — `.callout`, `.inline-note`, `.status-box`, `.bank-import-status`, `.info-box`/`.alert-box` all share the same left-border-panel pattern; extract a shared base class and migrate templates to `.callout` (needs care: padding/margin semantics vary per variant)
- [ ] **Hardcoded hex colors in CSS classes** — stat-card gradient variants (`.stat-card.secondary`, `.success`, `.warning`, etc.), tag/tag-mini color swatches, `.badge-active`/`.badge-inactive`, `.priority-badge.*`, `.cn-tag-*`, `.metric-card.*`, `.status-card.*`, `.agenda-item.*` — convert to `var(--color-*)` tokens (large surface, risk of dark-mode regressions if done carelessly)

---

## 🌿 Gardening (kleine Verbesserungen, kein Zeitdruck)

Kleine UI/UX-Fixes und Verbesserungen ohne hohe Priorität.
**Hinweis**: Dieser Abschnitt wird nie gelöscht — nur einzelne Items werden entfernt, wenn sie erledigt sind.
