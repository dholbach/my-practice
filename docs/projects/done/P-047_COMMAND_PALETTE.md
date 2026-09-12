# P-047 — Command Palette (⌘K)

**Status**: DONE (all three phases) · **Issue**: [#77](https://github.com/dholbach/my-practice/issues/77)

Originally filed as "P-040" — that number belongs to [Sample Data](P-040_SAMPLE_DATA.md).
Renumbered to the lowest unused number per [PROJECTS.md § Project Numbering](../../../PROJECTS.md#-project-numbering).

## Goal

Replace a wide nav bar with a command-first design: a handful of visible links
for the destinations opened daily, and everything else — navigation, search,
quick-create — one `⌘K` keystroke away.

Before: 8 top-level nav items, three of them hover dropdowns hiding ~20
list-level destinations. After: **four links**, and a palette that holds all of
them plus search and quick-create.

## What shipped

### Phase 1 — palette shell

- `templates/includes/command_palette.html` — the whole palette as server-rendered
  markup; `static/js/command_palette.js` only opens/closes, filters, searches and
  moves the selection
- `.cmd-palette*` in `tailwind.css`, `--color-*` tokens only (one new token,
  `--color-overlay`, for the modal scrim)
- `⌘K` / `Ctrl+K` to open, `Esc` to close (focus handed back to the opener),
  `↑`/`↓` to move with wraparound, `↵` to open, click-outside to dismiss
- **Springe zu** — 21 argument-free destinations; **Aktionen** — 8 quick-create links
- A visible 🔍 trigger in the header: the discoverability answer, and the only
  mobile story

### Phase 2 — search folded in

- The palette queries `/api/search/` (300ms debounce) and lists hits above the
  static entries, so `↵` opens the top match. **No backend change** — the API
  already returned a `type` per result.
- `global-search.js` and its 783-line test file deleted. Two things carried over
  rather than rewritten: the monotonic `latestRequestId` stale-response guard,
  and the intent behind `escapeHtml` (see "Decisions" below).
- `/` kept as an alias for opening the palette — it focused the old search box,
  and that is the muscle memory being inherited.
- The header controls (palette trigger, practice switcher, language/theme/privacy)
  now sit in a real `.header-controls` flex container in `base.html`, replacing the
  absolutely-positioned one `global-search.js` used to build at runtime. Three
  `float: right` declarations went away with it.

### Phase 3 — nav stripped

- Four links: **Übersicht, Klienten, Rechnungen, Focus Queue**. The Invoices,
  Finances and Admin dropdowns are gone; Anfragen moved into the palette.
- `keyboard-nav.js`: the single-letter global keys (`c`/`i`/`d`/`a`/`p`), the
  `title=` shortcut hints on nav links and the auto-fading corner toast all
  retired. The `?` overlay stays and now documents the palette; the contextual
  `n`/`e` keys stay because they act on the record already on screen, which the
  palette has no way to express.
- The overlay's appearance moved from `style.cssText` into `.kbd-help*` in
  `tailwind.css` — it was the last UI in the codebase built from inline styles
  with hardcoded colours.

## Decisions worth remembering

**Why a template partial rather than another DOM-building IIFE.** Two standing
rules postdate the original issue, and `global-search.js`/`keyboard-nav.js`
violated both (whole UIs built from `style.cssText` with literal
`rgba(0,0,0,0.8)`): the i18n guardrail cannot see a string that lives in a `.js`
file, and all CSS belongs in `tailwind.css` with `--color-*` tokens. Rendering
the palette server-side satisfies both at once and keeps the testable JS surface
small. Filtering reads each item's own `textContent`, so no label is duplicated
into a `data-*` attribute where it could drift.

**`escapeHtml` was not ported — it was designed out.** It existed because
`global-search.js` built result rows as an `innerHTML` string, and client names
legitimately contain `&` and `<`. Search rows are now `createElement` +
`textContent`, which removes the class of bug rather than guarding against it.
There is a test asserting a label containing both characters survives verbatim.

**Only argument-free destinations belong in the palette.** An entry is a plain
`<a href>`, so anything needing a pk or a type segment (client detail, the
operational checklist at `backups/checklist/<type>/`) has nowhere to get one.
Drill-down pages reached from a destination already listed (`/bank/review/`,
`/bank/withdrawals/`) were left out to keep the list scannable.

**The `?` overlay was kept, not folded into the palette footer** as the issue
sketched. The footer documents the palette's own keys, which are global; the
overlay additionally documents the contextual `n`/`e` keys, which depend on the
page. Merging them would have meant either dropping that documentation or
teaching a global server-rendered partial about `resolver_match`.

**String reuse kept the translation cost near zero.** 21 of the 24 strings the
palette needed already had msgids; across all three phases only five were new
("Command palette", "Jump to", "Navigate", "Search results", "Open command
palette"). Both fuzzy guesses `makemessages` produced were wrong in exactly the
way CLAUDE.md warns about — "Open command palette" → "Befehlspalette", "Search
results" → "Keine Ergebnisse" — and were corrected by hand.

## Known gap (follow-up)

The unmatched-bank-transaction count used to ride as a badge on the Finances
dropdown, and it is the **only** alert for bank work waiting to be assigned —
nothing in the Focus Queue or the dashboard surfaces it. Rather than lose it, the
nav grows a conditional fifth link (`🏦 Bank import` + count) only while the count
is non-zero; the rest of the time the nav is four links.

The proper home is a Focus Queue task type (`TaskType.BANK_UNMATCHED` in
`models/todo.py` plus a `sync_focus_queue_tasks` branch), at which point the
conditional nav link can go. Not done here — it needs a model choice, a
migration and a sync branch, none of which belong in a nav refactor.

## Tests

- `static/js/command_palette.test.js` — 24 tests: open/close/toggle,
  `preventDefault` on the browser's own Ctrl+K, `/` alias and its typing guard,
  filtering, group hiding, empty/loading/error states, pre-selection, arrow
  wraparound, hover→selection, focus handoff, query reset, platform hint, debounce,
  result rendering and ordering, `&`/`<` in labels, the stale-response race,
  cancel-on-close.
- `static/js/keyboard-nav.test.js` — rewritten for the reduced surface, including
  a test that the retired letters no longer navigate and one asserting the overlay
  carries no inline `style=`.

Two bugs were caught by these tests while writing them:

1. A filter with no matches left `aria-selected` and the highlight class on a
   now-hidden item.
2. Multi-line `{# … #}` comments in the new templates would have rendered
   literally — Django's single-line comment tag does not span lines (the same bug
   as #412).
