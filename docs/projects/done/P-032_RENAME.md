---
name: P-032 Project Rename
status: WIP
updated: 2026-04-17
---

# P-032 — Project Rename: `payments` → `my_practice`

Rename all traces of the old project name across the full stack.

## Phase progress

| Phase | Scope | Status |
|-------|-------|--------|
| A | Python package `payments_app` → `my_practice` (bulk sed, ~900 hits, DB table/content-type renames) | ✅ Done (2026-04-17) |
| B | Docker container names + `PAYMENTS_DATA_DIR` env var + `dev.py` | ✅ Done (2026-04-17) |
| C | DB rename: `payments` → `my_practice` (ALTER DATABASE + ALTER USER via temp superuser); docker-compose defaults updated | ✅ Done (2026-04-17) |
| D | systemd service files (7 files + `install-system-jobs.sh`) | ✅ Done (2026-04-17) |
| E | Repo folder rename + update absolute paths in `.service` files | Deferred to P-024 (OSS release) |
| F | Docs cleanup — `payments` references in guides/architecture/operations | ✅ Done (2026-04-17) |

## Phase E — repo folder (deferred)

Low priority; only needed for the OSS release (P-024). The absolute paths in `.service` files
(`/path/to/your/my-practice`) will need updating when the repo is moved.
