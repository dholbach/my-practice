# P-047 — Command Palette (⌘K)

**Status**: WIP (Phase 1) · **Issue**: [#77](https://github.com/dholbach/my-practice/issues/77)

Originally filed as "P-040" — that number belongs to [Sample Data](../done/P-040_SAMPLE_DATA.md).
Renumbered to the lowest unused number per [PROJECTS.md § Project Numbering](../../../PROJECTS.md#-project-numbering).

## Goal

Replace a wide nav bar with a command-first design: a handful of visible links for
the destinations opened daily, and everything else — navigation, search,
quick-create — one `⌘K` keystroke away.

There are ~20 list-level destinations outside the four daily ones (Billing, Bank
import/review/expenses, Withdrawals, Expenses, Analytics, Tax year/quarter/workday
audit, Revenue report, Calendar import/approval, Time off, Supervision, Client
triage, Tags, Boilerplate, Checklist, Practice management, Django admin). Three
hover dropdowns is the current answer; a palette is a better one.

## What already exists

| Piece | Where | Reuse |
|-------|-------|-------|
| `c:`/`i:` prefixed search over clients, open inquiries, invoices | `views/search_views.py`, `/api/search/` | As-is. Already returns a `type` field per result (`client`/`inquiry`/`invoice`), so the palette can group results with **no backend change** |
| Header search box, debounce, stale-response guard, `escapeHtml` | `static/js/global-search.js` | Logic yes, DOM no (see below) |
| `/` focuses search, `?` help overlay, single-letter nav (`c`/`i`/`d`/`a`/`p`) | `static/js/keyboard-nav.js` | Folded into the palette in Phase 3 |
| Alpine.js, loaded globally | `templates/base.html` | The palette is an Alpine component |

`⌘K`/`Ctrl+K` is free: `keyboard-nav.js` bails on any modifier key. It still needs
`preventDefault()` — `Ctrl/⌘+K` is the browser's own search-bar shortcut.

## Constraints that shape the implementation

Three standing rules postdate the original issue and rule out the obvious
"another IIFE that builds DOM in JS" approach:

1. **CSS architecture (M-PAT-04/07)** — `global-search.js` and `keyboard-nav.js`
   build their whole UI from inline `style.cssText` with hardcoded values
   (`rgba(0,0,0,0.8)`, `width: 300px`). That predates the rule. Palette styling
   goes in `tailwind.css` as `.cmd-palette*` classes using real `--color-*`
   tokens — `tests/test_css_tokens.py` fails on invented ones.
2. **i18n (P-039)** — no user-facing string may live in a `.js` file; the
   guardrail can't see them. `<body>` already carries 20 `data-*` label
   attributes and a palette needs 15–25 more.
3. **JS tests** run as bare `node <file>.test.js` against hand-rolled DOM stubs,
   no jsdom or jest. `global-search.test.js` is 783 lines, `keyboard-nav.test.js`
   530 — both written against the current imperative DOM-building.

All three point the same way: **render the palette as a Django template partial**
(markup, labels, jump targets and actions as ordinary `{% trans %}` HTML) and let
the JS only open/close, filter and keyboard-navigate it. Labels become
translatable for free, styling lands in `tailwind.css`, and the testable JS
surface stays small.

## Phases

### Phase 1 — palette shell (nothing removed)

- `templates/includes/command_palette.html` — Alpine component, all static
  entries rendered server-side and wrapped in `{% trans %}`
- `.cmd-palette*` classes in `tailwind.css`, `--color-*` tokens only
- `⌘K` / `Ctrl+K` to open, `Esc` to close, `↑`/`↓`/`↵` to navigate, click-outside
- **Springe zu** — the ~20 non-nav destinations
- **Aktionen** — quick-create links (`invoice_create`, `client_intake`,
  `inquiry_create`, `expense_create`, `withdrawal_create`, `todo_create`,
  `timeoff_create`, `tag_create`); all plain GET URLs, so `href`-only
- A visible trigger button in the header — the discoverability answer, and the
  only mobile story (the nav has no responsive treatment today)
- Existing header search box left untouched

Shippable on its own.

### Phase 2 — fold search in

- Query `/api/search/` from the palette, results grouped by `result.type`
- **Port, don't rewrite**, two things from `global-search.js`: the monotonic
  `latestRequestId` stale-response guard (`:36-45`) and `escapeHtml` (`:21-29`).
  Both are real bug fixes with comments explaining why.
- Then delete `global-search.js` and its test file

### Phase 3 — strip the nav

- Four top-level links; drop the Invoices / Finances / Admin dropdowns
- Fold the `?` help overlay into the palette footer
- Retire the redundant single-letter shortcuts and the auto-hiding
  bottom-right hint toast (`keyboard-nav.js:305-360`)

## Open decisions

- **Which four links.** The issue proposed Übersicht / Klienten / Rechnungen /
  Anfragen, but Focus Queue (P-050) landed since and is the daily driver.
  Suggested: Übersicht, Klienten, Rechnungen, Focus Queue — with Anfragen moving
  into the palette. Needed before Phase 3, not before Phase 1.
- **Practice switcher and the lang / theme / privacy toggles.** Stateful, and one
  is a POST form — they stay header buttons for now. Could become palette
  commands later.
