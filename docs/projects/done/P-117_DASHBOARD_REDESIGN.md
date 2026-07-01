# P-117 Dashboard Redesign

**Status**: Done  
**Completed**: July 2026  
**PRs**: #134, #136, #138, #139, #140, #145

## Goal

Replace the old monolithic dashboard (chart-heavy, passive) with an operational cockpit focused on what needs attention today.

## What Was Built

### Chunk 1 — ActionQueueBuilder (#134)
`ActionQueueBuilder` aggregates items from five widget builders into one ranked queue:
- Priority 1 (red): overdue invoices, tax prepayment missing
- Priority 2 (amber): drafts ready to send, clients needing attention, pending checklists
- Priority 3 (blue): bank import reminder

### Chunks 2+3 — Stats Strip + Two-Pane Layout (#136)
- **Stats strip**: year revenue, year profit, outstanding (count + amount, warns when >0), time off
- **Quick-action buttons**: "+ Neue Rechnung" / "+ Neue Klient:in" top-right
- **Two-pane console**: left pane (Heute agenda + Diese Woche focus), right pane (Braucht Aktion queue)
- **Capacity monitoring widget**: conditional — only shown when capacity warning is active
- **Multi-practice overview**: retained for users with multiple practices

### Chunk 4 — Charts Moved to Analytics (#138)
- Removed monthly bar chart from dashboard (Analytics already has a better line chart)
- Moved session heatmap from dashboard to Analytics → Clients tab
- Wrapped `analytics.html` with full Django i18n (~80 new msgids)
- `extra_heatmap_query` → `heatmap_url_prefix` pattern so heatmap pagination preserves tab state

### Post-merge Cleanup
- **#139**: Fixed two tests that hardcoded old dashboard context keys and a hyphen vs en-dash mismatch
- **#140**: 8 simplifications — currency format bug fix, `_make_invoice_item`/`_make_client_item` factories, heatmap conditional guard on non-clients tabs, gebueh helpers moved to `utils/`, 5× template conditional collapsed to prefix variable
- **#145**: Action queue grouping to match design — overdue invoices grouped into one row with total + client codes + age, drafts grouped, checklists grouped; inactive clients show exact days + last-session date + "Kontakt" button; "nach Dringlichkeit" sort hint in header

## Remaining (not in scope)

- "Heute" widget: design shows sessions and tasks in visually distinct sections; current renders them in a unified list (acceptable for real data density)
- "Diese Woche": design shows a compact day-column count grid; current shows the full weekly session list
