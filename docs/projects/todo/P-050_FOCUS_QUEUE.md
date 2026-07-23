# P-050: Focus Queue (Unified Task Model)

**Status**: TODO (concept/planning stage — not yet scoped for implementation)
**Priority**: Low/Mid-term
**Estimated effort**: TBD — likely split into sub-projects once scoped
**Created**: July 2026 (rescoped 2026-07-23)

---

## Goal

Introduce a single `Task` model that becomes the one place "things that need doing"
live — replacing scattered ad-hoc signals (a "missing-session-log" style tag on
`Client`, live-computed open/unsent-invoice checks) with real, stateful rows that
support snooze/priority/notes/tracking.

This is now the **core** of P-050. The rest follows from it:

- **Dashboard** (P-117) stays focused on *overview* — stats, revenue, at-a-glance
  state of the practice. It stops trying to also be the "needs action" list.
- **Focus Queue** (new nav item) becomes the single working surface that surfaces
  open `Task` rows — sorted by priority/age — and lets the user snooze, complete, or
  annotate them. This is the answer to "what should I do next," where the dashboard
  answers "how is the practice doing." **Resolved (2026-07-23)**: the Focus Queue
  fully replaces two existing surfaces rather than living alongside them —
  1. the dashboard's "Braucht Aktion" pane (`ActionQueueBuilder`, P-117), and
  2. the existing `/todos/` page (`PracticeTodo` model + `TodoListView` etc.) —
     both are subsumed, not kept as parallel systems.

---

## Problem with the current approach

- "Needs action" signals are scattered: some computed live from models (open
  invoices, invoices to send), some don't exist as structured data at all (quarterly
  review, supervision prep), and at least one is tracked via an ad-hoc tag on
  `Client` rather than a first-class record.
- No stateful layer for per-item metadata (priority, snooze, notes) on the computed
  items, since they're recomputed fresh each time rather than persisted.
- The dashboard has been carrying both jobs — overview *and* action list — which
  is why neither fully works as a queue to actually work through.

---

## Proposed Architecture

### `Task` model — extend `PracticeTodo`, don't start from scratch

`app/my_practice/models/todo.py` already has a `PracticeTodo` model
(practice-scoped, `title`/`description`/`category`/`priority`/`is_focus`/
`due_date`/`completed_at`) backing `/todos/`. It's most of the way to what `Task`
needs to be — this should be an **extension/rename**, not a parallel new model:

| Field | Status |
|---|---|
| `title`, `description`, `category`, `priority`, `due_date`, `completed_at` | already exist on `PracticeTodo` — keep as-is |
| `is_focus` | already exists — folds into "focus queue" selection, may become redundant once the queue itself is the focus view |
| `task_type` | **new** — enum: `manual`, `missing_session_log`, `invoice_unpaid`, `invoice_unsent`, `supervision`, `recurring_review`, `operational_checklist`, … (extensible — "and more" per Daniel, not a closed list). Existing `PracticeTodo` rows migrate as `task_type="manual"`. |
| `snoozed_until` | **new** — status becomes derived (open / snoozed-while-`snoozed_until`-in-future / done via `completed_at`) rather than a separate field |
| `related_object` | **new** — optional generic FK (e.g. `Client`, `Invoice`) so derived tasks link back to their source instead of duplicating info in `title`/`description` |

**Derived types** (`missing_session_log`, `invoice_unpaid`, `invoice_unsent`) are
**materialized** as real rows via a sync step (management command and/or model
signal), not computed fresh on every read. This is the fix for the tag-abuse
problem: a real row means a stable place to attach priority/snooze/notes, while the
open/closed state is still reconciled against the real underlying data (e.g. session
log gets added → task auto-closes), so there's no duplicated source of truth for
*whether* something is still outstanding — only for the metadata layered on top.

The logic to detect each of these already exists and doesn't need to be
re-derived — it currently lives in the widget builders that feed
`ActionQueueBuilder` (`utils/action_queue_builder.py`): `InvoiceActionsWidgetBuilder`
(unpaid/unsent invoices), `ClientAttentionWidgetBuilder` (likely owns the
missing-session-log signal today), `TaxQuarterWidgetBuilder`,
`BankImportReminderWidgetBuilder`, and **`ChecklistWidgetBuilder`** (operational
checklists — backups, security review — folds in too, per Daniel 2026-07-23). The
sync step should call into these (or their underlying queries) to decide which
`Task` rows to create/close, rather than reimplementing the detection logic.

`ChecklistWidgetBuilder` is a good fit for the same materialize-and-reconcile
pattern despite its different shape (cadence-based, practice-wide, not tied to a
`Client`/`Invoice`): it already has a period-based "is this done yet" model
(`OperationalChecklistCompletion` + `ChecklistItemPause` in
`models/operational.py`) — a `Task` row per pending `(checklist_type, period_start)`
gets created when the sync step sees no completion record for the current period,
and auto-closes the same way the others do once `OperationalChecklistCompletion` is
written. `related_object` can't point at a single model instance the way
`Client`/`Invoice` do here, so this type instead carries `checklist_type` +
`period_start` as plain fields (or packed into `notes`/a small JSON field) rather
than a generic FK.

**Manual/recurring types** (`supervision`, `recurring_review`) are created directly,
no sync needed.

**Open question**: `recurring_review` semantics. v1 candidate: manual recreate (user
re-adds a "Q3 review: client XY" task themselves). v2 idea (not needed yet):
auto-spawn next instance on completion, track "last reviewed" per client. Not a
blocker for v1 — revisit once the base queue is in use.

### Focus Queue UI

A new nav item / page surfacing open (non-snoozed, non-done) `Task` rows sorted by
priority/age, with actions to snooze, complete, or add notes. It replaces both
`/todos/` and the dashboard's "Braucht Aktion" pane as a single merged queue —
manual tasks and derived/materialized tasks sorted together, not two lists. This is
the primary deliverable of v1 — no session/timer mechanic required for it to be
useful on its own.

---

## Non-Goals (v1)

- No auto-spawning recurring tasks
- No pomodoro/timer mechanic unless the plain queue proves insufficient
- No mobile/offline support

---

## Open Questions

- [ ] Full `task_type` taxonomy — list above is a starting draft, not final
- [ ] `recurring_review` semantics (see above) — punt to v2. Note:
      `operational_checklist`'s period-based completion model
      (`OperationalChecklistCompletion`) may be a reusable pattern for this too,
      once it exists — worth revisiting `recurring_review` after
      `operational_checklist` ships rather than designing both from scratch.
- [ ] Migration path for existing `PracticeTodo` rows/URLs (`/todos/...`) — rename
      model in place vs. new model + data migration; redirect old URLs or remove them

---

## Suggested Phasing (once approved)

1. ✅ **Extend `PracticeTodo` → `Task`** — add `task_type`, `snoozed_until`,
   `related_object`; migrate existing rows to `task_type="manual"`. (PR #265)
2. ✅ **Materialize derived types** — `sync_focus_queue_tasks` management command
   creates/closes `Task` rows for missing-session-log, unpaid/unsent invoices, and
   pending operational checklists, reusing the existing widget builders' detection
   logic (`ClientAttentionWidgetBuilder.get_missing_session_log_clients()`,
   `InvoiceActionsWidgetBuilder.get_overdue_invoices()`/`get_draft_invoices()`,
   `ChecklistWidgetBuilder`). `/todos/` filters to `task_type="manual"` in the
   meantime so materialized rows stay invisible until phase 3. Not yet wired to a
   scheduled job — run manually until the Focus Queue UI exists. (PR pending)
3. **Focus Queue page** — new nav item, the working surface pulling from the merged
   `Task` queue (snooze/complete/notes). Retire `/todos/` and the dashboard's
   "Braucht Aktion" pane (`ActionQueueBuilder`) once this exists; pare the dashboard
   back down to pure overview.
