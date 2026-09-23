# ADR-0006: The minimum supported window is 768px, and wide tables scroll

## Context

This is practice software for a desktop. Nobody bills a client from a phone, so
a full mobile layout would be effort spent on a case that does not happen. But
two cases that *do* happen were never designed for:

- a small laptop screen;
- the window dragged to half the desktop, with something else running beside it.

Neither was covered. Every breakpoint in `tailwind.css` had been written ad hoc
(600, 640, 768 and 900px all appear), and the layouts between them were never
checked. The bug that surfaced this was `.cn-session-actions` on the client
detail page: a `flex-shrink: 0` block inside a flex row, so it sized to
max-content and painted its buttons outside the card. Two others of the same
shape were live at the same time (`.client-actions-left`, ~620px of buttons),
and a fourth (`.cn-note-actions`) was dead code with the same defect.

Tables were worse: 36 of 39 had no scroll container. And the obvious fix is a
trap. `.table-container table` is `width: 100%`, so wrapping a table in an
`overflow-x: auto` div changes **nothing** — the table shrinks to the container
and crushes its columns exactly as before, while the markup now looks correct.
`invoice_list` declares 820px of column widths across six columns and quietly
squeezed them to fit.

## Decision

**The minimum supported viewport is 768px** — 736px of content once `body`'s
1rem side padding is removed. Above it nothing may overflow horizontally. Below
it, nothing is promised.

Three rules follow, enforced by `my_practice/tests/test_responsive_layout.py`
(M-PAT-09):

1. **Every flex button group declares `flex-wrap: wrap`.** Wrapping is never
   worse than overflowing, and at full width it changes nothing. The allowlist
   is empty.
2. **Every `<table>` has `<div class="table-container">` as its immediate
   parent.**
3. **A table of 6+ columns also carries `table-container--wide`**, which sets
   `min-width: 700px` on the table. This is the part that does the work: the
   700px is what `overflow-x` has to scroll against. It sits just below the
   736px content box, so it is inert at every supported size and engages only
   when the window is dragged smaller.

768px was chosen because it is half of a 1536px laptop and close to half of the
common 1366 and 1600px widths — the actual "news in one window, invoices in the
other" case. Phones are explicitly out of scope; `minmax(350px, 1fr)` grids and
400px form-field floors were left as they are because they only bite below the
supported range.

## Consequences

- `min-width: 700px` on a `width: 100%` table reads as redundant and is the
  obvious thing to delete while tidying. Deleting it silently restores the
  column-crushing — the markup still looks right and no test of the *markup*
  would notice. The guardrail's third check exists for precisely this, and the
  rule is repeated in a comment above `.table-container` in `tailwind.css`.
- `.data-table--wide` was removed; the container modifier replaces it. A table
  no longer opts into being wide — its column count decides, so a seventh column
  added to a five-column table fails the guardrail until the wrapper is updated.
- Six columns is a threshold, not a measurement. A five-column table with long
  free text can still crush; a six-column table of short numbers scrolls a
  little sooner than it strictly needs to. The threshold is cheap to enforce and
  errs toward scrolling, which is the recoverable failure.
- The checks read template and CSS source. They cannot see a width set from
  JavaScript, an inline `style`, or a long unbreakable string in real data. The
  standing advice is still to drag the window to 800px and look.
- Breakpoints remain inconsistent (600/640/768/900). This record does not
  change them; it only fixes the floor everything must clear.

Pattern reference: [CODEBASE_STANDARDS.md](../guides/CODEBASE_STANDARDS.md)
(M-PAT-09). Guardrail: `app/my_practice/tests/test_responsive_layout.py`.
