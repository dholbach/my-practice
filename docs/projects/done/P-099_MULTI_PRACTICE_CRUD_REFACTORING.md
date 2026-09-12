# P-099: Multi-Practice Architecture

**Status**: ✅ DONE
**Completed**: before the v0.1.0 public release (2026-06-16)

## What Was Done

Practice scoping shipped essentially as planned, letting one user manage multiple
separate businesses (e.g. Therapy + Coaching) with separate clients, invoices,
expenses, withdrawals, and settings:

- `UserPractice` M2M through-model (`models/practice.py`) with an `is_owner` flag
- `PracticeScopedQuerySet` / `PracticeScopedManager` (`models/base.py`) — every
  practice-specific model filters via `.for_current_practice(request)`
- `PracticeScopeMiddleware` (`config/middleware.py`) resolves the active practice
  from the session, falling back to the user's owned/first practice
- `switch_practice()` (`utils/practice_helpers.py`) + practice switcher UI
- All CRUD views scoped via the `PracticeScoped*View` mixins
  (`views/crud_mixins.py`) — see CLAUDE.md's "CRUD Views" section

## Deliberately Not Built

- **Combined cross-practice dashboard** — never shipped; each practice's data
  stays fully separate with no aggregate view. Not currently needed for the
  single-operator use case this app targets.
- **`ClientTag` stayed global (no practice FK)** — resolved the plan's open
  question deliberately: a single-operator can reuse the same tag vocabulary
  across practices without per-practice duplication (see the model's docstring
  in `models/tag.py`).

## Related

- [CODE_STRUCTURE.md](../../architecture/CODE_STRUCTURE.md) — current architecture
- [CLAUDE.md](../../../CLAUDE.md) — CRUD mixins reference
