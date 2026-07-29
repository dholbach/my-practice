# P-028: Dashboard Redesign — Weekly Focus Widget

**Status**: DONE
**Completed**: April 2026
**Superseded**: 2026-07-30 — see "Update" below; the `is_focus` field described here has been removed.

## Goal

Dashboard widget for the current week's tasks: mark a task as focus (⭐),
check it off (☐) directly in the widget, without leaving the page.

## Implemented

### Phase 1
- `is_focus` BooleanField on `PracticeTodo`
- HTMX toggle `/todos/<pk>/toggle-focus/` → star button in the todo widget
- `WeeklyFocusWidgetBuilder` in `utils/weekly_focus_widget.py`
- 2-column dashboard grid (daily agenda left, weekly focus right)
- ⭐ button in `todo_content.html` and the new `weekly_focus_widget_content.html`

### Phase 2 (follow-up)
- ☐ complete button directly in the weekly focus widget
- Both buttons (`☐`, `⭐`) replace the whole widget fragment via
  `hx-target="#weekly-focus-content"` + `hx-swap="outerHTML"`
- `ctx=weekly_focus` query parameter on `todo_toggle_complete` and
  `todo_toggle_focus` (calls `WeeklyFocusWidgetBuilder`)
- CSS: `.weekly-focus-task-item`, `.btn-focus-complete`

## Update (2026-07-30): `is_focus` retired, merged into `due_date`

The `/todos/` list page (P-050 phase 4) had already removed the only UI path
to *set* `is_focus=True` — the star only survived here as a "remove focus"
action, leaving no way to add a task to this widget at all. Rather than
restoring a second star toggle, `is_focus` was retired outright and this
widget now lists tasks with `due_date <= today` — the same "due today or
overdue" signal the Focus Queue (P-050) already used to sort its own queue,
set via that page's "📅 Today" quick action. See
[P-050_FOCUS_QUEUE.md](P-050_FOCUS_QUEUE.md), which had flagged `is_focus`
as likely-redundant once the queue existed.

- `todo_toggle_focus` view, its URL, and the `is_focus` field are removed
  (migration `0018_remove_practicetodo_is_focus`).
- `WeeklyFocusWidgetBuilder._get_due_today_tasks()` (renamed from
  `_get_focus_tasks`) filters `due_date__lte=today` instead of `is_focus=True`.
- The widget is now read-only for tasks — due dates are managed from the
  Focus Queue, not from this widget's star button (which no longer exists).

## Files

- `app/my_practice/models/todo.py` — `PracticeTodo` (`is_focus` removed)
- `app/my_practice/views/todo_views.py` — `todo_toggle_complete`
- `app/my_practice/utils/weekly_focus_widget.py` — `WeeklyFocusWidgetBuilder`
- `app/templates/includes/weekly_focus_widget_content.html` — widget partial
- `app/static/css/tailwind.css` — widget styles (`@layer components`)
