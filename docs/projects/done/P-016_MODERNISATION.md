# P-016: Stack Modernisation

**Status**: ✅ DONE
**Completed**: 2026-04-01
**Priority**: LOW–MEDIUM (per item)
**Created**: 2026-03-04
**Cross-ref**: [PROJECTS.md](../../../PROJECTS.md)

Collected modernisation opportunities from the Q1 2026 code quality pass.
Each item is independent — tackle in any order, or skip if the tradeoff isn't worth it.

---

## DONE

| Item | Summary | Completed |
|------|---------|-----------|
| M-01 | PostgreSQL FTS — `SearchVector`/`SearchQuery`/`SearchRank` (German stemming) on invoice, client, and global search | 2026-03-04 |
| M-02 | `LoginRequired` removed (localhost-only app; auth unnecessary) | 2026-03-04 |
| M-03 | psycopg3 already in use — no action needed | — |
| M-06 | Django upgraded: 5.2 LTS | 2026-03-16 |
| M-07 | CSS nesting applied across all static CSS files | 2026-03-17 |
| M-08 | ruff bumped to 0.15.6; zero new violations | 2026-03-17 |
| M-09 | `StrEnum` applied to all model choices (`Invoice.Status`, `Client.Language`, `PendingCalendarEvent.Status`, etc.) | 2026-03-17 |
| M-10 | Django upgraded: 6.0.3 | 2026-03-17 |
| M-14 | Badge color token palette (12 semantic colors × bg/text/border, light+dark) added to `common.css`; `inquiry_list.css` refactored to use tokens — removed 18 `[data-theme="dark"]` hardcoded overrides | 2026-03-31 |
| M-05 | HTMX adopted for interactive UI (partial page updates via `hx-*` attributes) | 2026-04-01 |
| M-13 | Inline `style=""` audit — replaced with CSS classes opportunistically alongside template work | 2026-04-01 |

---

## Excluded / Won't Do

| Item | Reason |
|------|--------|
| `uv` package manager | Adds complexity to Docker build; pip sufficient for single-container app |
| `dataclasses` for builder return types | Dicts are fine; over-engineering for a single-user app |
| M-04 Async email | 1–2s SMTP RTT imperceptible for single user; not worth the complexity |
| M-12 Background tasks | Same problem as M-04; IMMEDIATE backend = no benefit over current sync approach |
| M-11 Phase 2 (CSP strict) | No threat model on localhost single-user app; security theatre |
