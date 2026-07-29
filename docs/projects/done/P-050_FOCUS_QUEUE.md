# P-050: Focus Queue (Unified Task Model)

**Status**: DONE (2026-07-24) — shipped in v0.4.0
**Priority**: Low/Mid-term
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
   meantime so materialized rows stay invisible until phase 3. (PR #266)
3. ✅ **Focus Queue page** — new nav item ("Im Fokus" in German), `/focus/`, a single
   merged queue of manual + materialized `Task` rows sorted by priority then age,
   with complete/snooze (+1d/+3d/+1w presets)/edit actions and a filter-by-`task_type`
   dropdown. Verified end-to-end against the running dev server (login, practice
   switch, filter, complete, snooze, empty state — all in German with correct
   translations). (PR #267)
4. ✅ **Retire `/todos/` + dashboard's "Braucht Aktion" pane** — `/todos/` list
   page removed (`TodoListView`, `todo_list.html`, `includes/todo_content.html`);
   `TodoCreateView`/`TodoUpdateView`/`TodoDeleteView`/`todo_toggle_complete`/
   `todo_toggle_focus` kept (Focus Queue reuses the create/edit form; the two
   toggle endpoints are still used inline by the dashboard's Agenda/WeeklyFocus
   widgets). Dashboard's `ActionQueueBuilder`/"Needs Action" pane removed —
   along with `TaxQuarterWidgetBuilder`/`BankImportReminderWidgetBuilder`
   (fully dead once `ActionQueueBuilder` was gone: nothing else called their
   `build_context()`/`get_action_items()`) and the now-dead `get_action_items()`
   methods on `InvoiceActionsWidgetBuilder`/`ClientAttentionWidgetBuilder`/
   `ChecklistWidgetBuilder` (those three classes stay — still used by
   `sync_focus_queue_tasks`). Dashboard's Today/This Week widgets now render as
   plain stacked full-width blocks instead of a two-pane grid. (PR pending)

P-050 is now feature-complete: unified `Task` model, materialization, and the
Focus Queue page as the single surface for what needs doing.

## Post-v1 follow-ups (2026-07-23 – 2026-07-24)

Shipped after the 4 core phases above, in response to real usage:

- **Session-level missing-log tasks + reference dates** (PR #269): the
  `missing_session_log` signal moved from Client-level to per-Session, so each
  task points at the specific session missing a log rather than just flagging
  the client. Added a `reference_date` property (invoice date / session date /
  task creation date, whichever applies) shown on every Focus Queue row, and a
  `related_object_url` special case linking straight to creating that session's
  log. Also fixed a dark-mode badge-contrast issue.
- **Retire `missing-session-log` client tag + client-linked task creation**
  (PR #270): the tag became fully redundant once the per-session task existed,
  so it was removed from `update_client_tags.py` (data migration deletes
  existing tag rows). A "+ Task" button on the client detail page creates a
  manual task pre-linked to that client (`?client=<pk>` on `TodoCreateView`),
  covering the "quick ad-hoc reminder for this client" case the tag used to
  half-serve. `ClientAttentionWidgetBuilder`, dead since PR #268, was deleted.
- **Focus Queue type-filter UX**: dropdown replaced with color-coded pill
  buttons matching each task type's badge color, with counts and a
  greyed-out/empty state; colors tuned for dark-mode contrast.
- **Fixed a live crash** (`'Client' object has no attribute 'session_date'`):
  materialized tasks created before the missing-session-log signal moved to
  Session-level still pointed at a `Client`. `reference_date` now keys off
  `content_type.model` instead of assuming a model from `task_type`, and
  `sync_focus_queue_tasks`'s auto-close logic now retires stale rows
  regardless of which model they originally pointed at.
- **Wired `sync_focus_queue_tasks` to a daily systemd timer** (2026-07-29):
  `scripts/my-practice-sync-focus-queue.timer`/`.service`, documented in
  `docs/operations/SCRIPTS.md` — closes the one gap this doc had flagged as
  unfinished. Materialized tasks now stay fresh without a manual run.
- **Checkbox in the queue now really toggles** (2026-07-29): it previously
  only ever called `mark_completed()`, so an accidental click had no way
  back except Django admin. The endpoint now toggles complete/incomplete and
  swaps just the one row (`includes/focus_queue_row.html`), so a
  just-completed task stays visible — struck through, checkbox still
  checked — as an immediate undo affordance.
- **"📅 Today" quick action + due-date-aware sort** (2026-07-30): `due_date`
  previously only decorated a row; it now also drives sort order — tasks due
  today or overdue always rank above the rest of the queue regardless of
  priority tier. A new button next to the snooze presets sets `due_date` to
  today in one click.
- **`is_focus` retired, folded into `due_date`** (2026-07-30): resolves the
  overlap flagged in line 56 above and in issue #281. The `/todos/` list
  page's retirement (phase 4) had already removed the only UI path to *set*
  `is_focus` — the dashboard's weekly widget star only ever did "remove
  focus" from then on, with no way to add a task to it. Rather than
  restoring a second star toggle, `is_focus` was removed outright
  (migration `0018_remove_practicetodo_is_focus`) and the dashboard widget
  now lists `due_date <= today` tasks — the same signal the Focus Queue
  itself sorts on. `todo_toggle_focus` and its URL are gone; see
  [P-028_DASHBOARD_WEEKLY_FOCUS.md](P-028_DASHBOARD_WEEKLY_FOCUS.md) for the
  widget-side detail.
