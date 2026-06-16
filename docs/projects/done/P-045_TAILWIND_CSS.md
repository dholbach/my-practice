# P-045: Tailwind CSS — Design System Migration

**Status**: WIP — Phase 0 ✅, Phase 1 ✅, Phase 2 ✅, Phase 3 ✅, Phase 4 ongoing
**Priority**: Medium (deliberate, not opportunistic)
**Risk**: Medium — needs planned setup; safe to do incrementally once scaffolding is in place
**Effort**: ~1–2 days setup + months of gradual per-template migration

## Goal

Replace the hand-rolled CSS variable / utility system with Tailwind CSS 4, permanently
eliminating the dark-mode maintenance problem class and reducing per-feature CSS files
to near-zero.

## Why

- **Dark mode**: Tailwind 4's `dark:` variant + CSS variable integration eliminates
  the current per-property dual-declaration pattern. One migration, done.
- **CSS debt**: 29 CSS files, ~9 400 lines. Most selectors are single-use layout/spacing
  rules Tailwind renders unnecessary.
- **Velocity**: Once migrated, new UI requires no new CSS files — just utility classes
  in templates.
- **Migration path is unusually clean**: The existing CSS variable system maps almost
  directly to Tailwind 4's `@theme` block.

## Decided Architecture

### Dark mode — option (a): `@custom-variant`

The app uses a JS toggle (`localStorage` → `data-theme="dark"` on `<html>`), not
`@media (prefers-color-scheme: dark)`. Tailwind 4's `dark:` defaults to the media
query; one config line fixes this:

```css
@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));
```

Zero JS changes. User toggle is preserved. Every `dark:` class tracks the existing
attribute.

### Build tool — `@tailwindcss/cli` in Docker

- No `package.json` exists yet; either tool requires introducing Node.js
- Vite ruled out for now — strictly more than needed; revisit if Alpine ever needs a
  bundler (see note below)
- `@tailwindcss/cli` watcher runs as a sidecar in the dev Docker container, started
  by `./dev.py start`
- One `package.json`, one `Dockerfile` line, one `./dev.py` change for Phase 0

**Alpine CDN note**: Alpine is currently vendored locally (`static/js/alpine.min.js`).
Once a Node.js build step exists for Tailwind, it becomes easy to also bundle Alpine
via npm rather than vendoring the minified file manually. Worth revisiting at that
point — not a dependency or blocker.

### Preflight — disabled in Phase 0

Tailwind's preflight resets browser defaults aggressively (strips list styles, heading
sizes, button appearance, etc.). `common.css` relies on some browser defaults.
Disable preflight entirely for Phase 0 so the existing CSS continues to work unchanged:

```css
@import "tailwindcss" no-preflight;
```

Revisit preflight once the per-page CSS files are mostly gone and the blast radius of
enabling it is knowable.

### Scope — hybrid steady state

Full elimination is months of work across 29 files. Goal is:
- Tailwind handles all **new** UI from Phase 1 onward
- Old CSS files are **thinned opportunistically** when their template is touched
- A file is deleted when it no longer contains anything that can't be expressed as
  Tailwind utilities

## CSS variable scope

Light-mode tokens belong in `@theme`; dark-mode overrides go inside the
`@custom-variant dark` block. Order matters — define `@theme` first, then the variant.
Do NOT copy-paste the `[data-theme="dark"]` block from `common.css` into `@theme`;
split it correctly by mode.

## Phases

### Phase 0 — Setup (~1 day)

1. `package.json` with `tailwindcss` dev dependency
2. `app/static/css/tailwind.css` — `@import "tailwindcss" no-preflight` + `@custom-variant dark` + `@theme` block mapping existing CSS variables
3. `Dockerfile` — add Node.js, `npm ci`
4. `./dev.py start` — spawn `tailwindcss --watch` as sidecar alongside Django
5. `base.html` — add `tailwind.out.css` link (keep all existing CSS links intact)
6. Verify zero visual regression on 3–4 pages before touching any markup
7. CI / `./dev.py quality` — add `npm run build:css` so the compiled file stays current

**Gate**: Phase 1 does not start until Phase 0 passes a visual regression check.

### Phase 1 — Utility foundation

- Migrate `common.css` utilities to `@layer components` or inline Tailwind classes
- Keep `common.css` alive until every consumer is migrated; delete at end of phase

### Phase 2 — Per-page CSS removal (opportunistic)

**Status**: 25 of 29 files deleted. 4 large files remain.

**Completed (2026-06-15)**:
`delete_confirm.css`, `invoices.css`, `revenue_report.css`, `email_forms.css`,
`client_triage.css`, `client_list.css`, `invoice_forms.css`, `boilerplate.css`,
`todo_list.css`, `calendar_approval_queue.css`, `invoice_list.css`,
`monthly_billing_overview.css`, `tax_workday_audit.css`, `bank_import.css`,
`client_cards.css`, `calendar_import.css`, `bank_expense_review.css`,
`expense_form.css`, `expenses.css`, `checklist.css`, `bank_review.css`,
`tax_summary.css`, `dashboard.css`, `client_detail.css`, `inquiry_list.css`

**Phase 2 complete** — all 29 per-page CSS files deleted.

**Phase 3 — common.css deleted (2026-06-15)**:

All content from `common.css` merged into `tailwind.css`:
- `:root` + `[data-theme="dark"]` CSS custom properties → unlayered, before `@layer components`
- Global base styles (`body`, `a`, `h1–h6`) → `@layer base`
- Global component styles (`nav`, `.btn`, `.header`, `.dropdown`, etc.) → second `@layer components` block
- Utility aliases (`.d-none`, `.mt-*`, `.text-muted`, etc.) → unlayered, after `@theme`

`common.css` is **deleted**. Only two CSS files remain: `tailwind.css` (source) and `tailwind.out.css` (compiled).

### Phase 4 — Unified design language via @theme tokens

**Goal**: Replace the dual CSS variable / Tailwind utility split with a single @theme token system.
Every component uses semantic tokens (`bg-surface`, `text-text-primary` …); dark mode works through
CSS custom property inheritance — no `dark:` prefix needed in most templates.

**Foundation complete (2026-06-15)**:
- `@theme` block updated to use actual light-mode values (not CSS var proxies)
- `[data-theme="dark"]` now overrides `--color-*` token names only
- `:root` legacy vars are now aliases: `--card-bg: var(--color-surface)` etc.
- All 769 existing `var(--old-name)` references automatically dark-mode-aware through the chain
- Zero per-component changes required for this foundation step

**Architecture**:
```
@theme { --color-surface: #fff; }       ← source of truth
:root  { --card-bg: var(--color-surface); }  ← legacy alias (temporary)
[data-theme="dark"] { --color-surface: #2d3748; }  ← dark override
→ var(--card-bg) resolves to #2d3748 in dark mode ✓
```

**Full cleanup complete (2026-06-15)**:
- `global-search.js` and `keyboard-nav.js` and `bank_review.js` migrated to `--color-*` tokens
- All 30 legacy `:root` aliases removed — `:root` now contains only gradient vars + badge palette
- Zero `var(--old-name)` references anywhere in the codebase

**Phase 4 fully complete (2026-06-16)**:
- Badge colour palette (36 vars) moved from `:root` to `@theme` as `--color-badge-*` tokens
- Body gradient vars moved from `:root` to `@theme` as `--color-bg-gradient-*` tokens
- `:root` block entirely removed — `tailwind.css` now has no `:root` at all
- Only remaining non-`--color-*` vars: `--year-color` / `--year-text` (set dynamically by JS; intentionally kept)

## Constraints

- **Don't rush Phase 0**: a broken build blocks all development
- **No big-bang template rewrite**: one template per session max
- **`common.css` is gone** — all content now in `tailwind.css`
- **PDF templates exempt**: `invoice_pdf_*.html` require inline styles
- **Unified visual style**: as pages are migrated, collapse per-page table/badge
  variants onto the shared canonical classes rather than preserving the drift.
  `.data-table` (0.75rem padding) is the one true table; `.status-badge` is the
  one true pill. Per-page height overrides like `height: 56px` on table rows are
  a smell — remove them during migration.

## Success criteria

- Zero per-page CSS files remain (PDF templates excepted) ✅
- Single CSS source file (`tailwind.css`) — no separate `common.css` ✅
- New UI features need zero new CSS files ✅
- Dark mode requires no manual CSS — only `dark:` variants (Phase 4, deferred) ✅ (resolved via token chain; 13 hardcoded-hex inline styles replaced with semantic classes)
- **Zero legacy `var(--old-name)` references anywhere in the codebase** ✅
- **No `:root` block** — all CSS custom properties live in `@theme` (light) or `[data-theme="dark"]` (dark) ✅

## Related

- [P-044 Alpine.js](../done/P-044_ALPINE_JS.md) — complete; Alpine vendored locally
- [P-039 Django i18n](P-039_I18N.md) — unrelated but similar deliberate-migration shape
