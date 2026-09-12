# P-003: Workflow-Driven Dashboard Redesign

**Status**: ✅ DONE (Feb 2026), later substantially reworked
**Completed**: 2 Feb 2026

## What Shipped (Feb 2026)

Replaced a 4-page navigation flow (dashboard/analytics/client list/invoice
list) with a single-page dashboard of collapsible widgets:

- A combined Sessions + Tasks agenda widget, sorted chronologically
- Session Import, Client Attention, and Invoice Actions widgets
- A shared collapsible widget shell with LocalStorage-persisted
  expand/collapse state
- Session time tracking, so calendar-imported sessions carry a time, not just
  a date (the plan's "Option A: extend InvoiceItem" was superseded — time
  tracking ended up on a dedicated `Session` model, `models/session.py`,
  rather than `InvoiceItem`)

## Superseded Since

The dashboard architecture here was **replaced by the P-117 redesign**
(v0.2.7) — `dashboard_views.py` is now a thin dispatcher delegating to
`DashboardContextAssembler` and a different set of widget builders (see
CODE_STRUCTURE.md's "Dashboard architecture" section for the current list).
The Agenda widget this project introduced, along with several others built on
top of it, was itself retired during the P-050 phase-4 "Needs Action" pane
cleanup. Nothing from this project's specific widget implementation is still
in production — only the underlying `Session.session_time` field persists.

## Related

- [CODE_STRUCTURE.md](../../architecture/CODE_STRUCTURE.md) — current dashboard architecture (P-117)
- [P-117_DASHBOARD_REDESIGN.md](P-117_DASHBOARD_REDESIGN.md) and [P-050_FOCUS_QUEUE.md](P-050_FOCUS_QUEUE.md) superseded this project's widgets
