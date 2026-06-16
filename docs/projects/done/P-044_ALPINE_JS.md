# P-044: Alpine.js — Incremental Adoption

**Status**: DONE (2026-06-15)
**Priority**: Low (opportunistic — touch templates as you go)
**Risk**: None — CDN drop-in, zero build step, no migration required

## Goal

Replace vanilla JS event-handler boilerplate with Alpine.js `x-` directives so
behaviour lives next to the markup it controls. No component architecture change,
no bundler required — purely incremental and reversible.

## Why

- Eliminates the `inline-handlers.js` data-attribute indirection layer
- Behaviour is readable in-template (`x-on:change="$el.form.submit()"` vs
  `data-autosubmit` + a separate JS file)
- Foundation for future lightweight interactive islands without HTMX round-trips
- Zero-conflict with HTMX — both libraries co-exist cleanly

## Scope (in order)

### Phase 1 — Replace `inline-handlers.js` ✅ DONE

`inline-handlers.js` handled three data-attribute patterns. All migrated to
`x-on:` directives across 7 templates; file deleted.

| Pattern | Alpine equivalent |
|---------|-----------------|
| `data-autosubmit` on `<select>` | `x-data x-on:change="$el.form.submit()"` |
| `data-confirm="msg"` | `x-data x-on:click="confirm('msg') \|\| $event.preventDefault()"` |
| `data-nav-url="url"` on `<select>` | `x-data x-on:change="window.location.href = 'url' + $el.value"` |

### Phase 2 — Broader inline handler sweep ✅ DONE (Group A + B)

**Group A — trivial swaps (done):**
- `inquiry_list.html` — two filter-bar `onchange="this.form.submit()"` selects
- `billing_open_overview.html` — write-off confirm button
- `expense_form.html` — merge-form onsubmit confirm
- `client_triage.html` + `tax_workday_audit.html` — `window.print()` buttons
- `includes/inline_post_button.html` — confirm-on-submit partial

**Group B — small JS blocks deleted (done):**
- `inquiry_list.html` — `toggleAnalytics()` function replaced by `x-data="{ open: true }"` + `x-show`; `{% block extra_js %}` block deleted
- `inquiry_form.html` — `showEmailTemplate()` function replaced by `x-data="{ status }"` + `x-show` on cards; function deleted from JS block

**Group C — deferred (do when next touching these files):**
- `includes/email_card.html` — `bpCopy()` + `bpSwitchTab()` (backed by `email_card.js`; delete the file when done)
- `client_detail_tabs.html` confirms + collapse toggles (tab-switch `cnSwitchTab()` intentionally skipped — intertwined with chart redraws per M-PAT-03)
- `dashboard.html` practice-card `onclick` — fix: replace `<div onclick>` with `<a>` wrapping the card, not Alpine

### Phase 3 — Evaluate (after Phase 2 complete)

- `global-search.js` dropdown (good Alpine candidate)
- Any `widgets.js` sections that are pure DOM toggling

## Not in scope

- Chart rendering — stays in `chart_*.js` (custom Canvas API, not a DOM concern)
- HTMX interactions — HTMX handles server round-trips; Alpine handles client-side state
- Full component rewrite — this is progressive enhancement only

## How Alpine is loaded

CDN in `base.html` head, alongside HTMX:
```html
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
```

Pin to a specific patch version (e.g. `@3.14.3`) when reproducible deploys matter.
Switch to `package.json` + bundler if/when P-045 Tailwind introduces a build step.

## Related

- [P-045 Tailwind CSS](../todo/P-045_TAILWIND_CSS.md) — independent; Alpine does not depend on Tailwind
