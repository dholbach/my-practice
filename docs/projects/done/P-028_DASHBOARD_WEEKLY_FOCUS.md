# P-028: Dashboard Redesign — Weekly Focus Widget

**Status**: DONE
**Abgeschlossen**: April 2026

## Ziel

Dashboard-Widget für fokussierte Aufgaben der aktuellen Woche: Aufgaben als Fokus
markieren (⭐), direkt im Widget abhaken (☐), ohne die Seite zu wechseln.

## Umgesetzt

### Phase 1
- `is_focus` BooleanField auf `PracticeTodo`
- HTMX-Toggle `/todos/<pk>/toggle-focus/` → sofortiger Stern-Button im Todo-Widget
- `WeeklyFocusWidgetBuilder` in `utils/dashboard_widgets.py`
- 2-column Dashboard-Grid (Tages-Agenda links, Fokus-Woche rechts)
- ⭐-Button in `todo_content.html` und neuem `weekly_focus_widget_content.html`

### Phase 2 (follow-up)
- ☐ Complete-Button direkt im Weekly-Focus-Widget
- Beide Buttons (`☐`, `⭐`) ersetzen das gesamte Widget-Fragment via
  `hx-target="#weekly-focus-content"` + `hx-swap="outerHTML"`
- `ctx=weekly_focus` Query-Parameter in `todo_toggle_complete` und
  `todo_toggle_focus` (`WeeklyFocusWidgetBuilder` wird aufgerufen)
- CSS: `.weekly-focus-task-item`, `.btn-focus-complete` in `dashboard.css`

## Dateien

- `app/my_practice/models/todo.py` — `is_focus` BooleanField
- `app/my_practice/views/todo_views.py` — `todo_toggle_focus`, `todo_toggle_complete`
- `app/my_practice/utils/dashboard_widgets.py` — `WeeklyFocusWidgetBuilder`
- `app/templates/includes/weekly_focus_widget_content.html` — Widget-Partial
- `app/static/css/dashboard.css` — Widget-Styles
