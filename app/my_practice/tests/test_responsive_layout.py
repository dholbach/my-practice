"""Guardrails for narrow-window layout (M-PAT-09).

The target is not a phone. It is a small laptop screen, or a window dragged to
half the desktop while something else runs beside it — so the contract is a
minimum *supported* viewport of 768px, i.e. ``MIN_CONTENT_WIDTH`` of usable
content once ``body``'s 1rem padding is taken off both sides. Above that width
nothing may overflow horizontally; below it, only a table may scroll, and only
inside its own container.

Three failure modes, all invisible at desktop width and all with live instances
when this test was added:

1. **A button group that cannot wrap.** ``.cn-session-actions`` was a plain
   block with ``flex-shrink: 0`` inside a flex row, so it sized to max-content
   and simply ran past the card's right edge — the delete button was painted
   outside the panel. ``.client-actions-left`` held ~620px of buttons the same
   way. Nothing renders differently until the window is narrow enough, so the
   bug ships and is only ever seen by whoever happens to resize.

2. **A table with no scroll container.** 36 of 39 tables had none. Because
   ``.table-container table`` is ``width: 100%``, a table always shrinks to its
   container and the columns crush instead — ``invoice_list`` declares 820px of
   column widths across six columns and silently squeezed them to fit.

3. **A table wrapped but with nothing to scroll against.** The wrapper alone is
   a no-op for a ``width: 100%`` table: ``overflow-x`` never triggers because
   the table never exceeds the container. A wide table needs an explicit
   ``min-width`` for the container to earn its keep, which is what
   ``.table-container--wide`` supplies. This is the subtle one — the markup
   looks correct and the behaviour is unchanged. See ADR-0006.

All three lists are ratchets: shrink them, never grow them to make a new render
pass. Note the checks read source only — they cannot see a width set from
JavaScript, an inline ``style="width:…"``, or a long unbreakable string in real
data. When in doubt, drag the window to 800px and look.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

CSS_PATH = Path(settings.BASE_DIR) / "static" / "css" / "tailwind.css"
TEMPLATE_DIR = Path(settings.BASE_DIR) / "templates"

# The narrowest window the UI is expected to work in, and the content width that
# leaves once body's 1rem side padding is removed. Not a phone — a half-screen
# laptop window. See ADR-0006.
MIN_SUPPORTED_VIEWPORT = 768
MIN_CONTENT_WIDTH = MIN_SUPPORTED_VIEWPORT - 32

# A table this wide no longer fits MIN_CONTENT_WIDTH at a readable column size,
# so its container must carry the --wide modifier and scroll instead of crush.
WIDE_TABLE_COLUMNS = 6

# PDF templates lay out against a fixed paper width and never reflow.
EXEMPT_TEMPLATES: frozenset[str] = frozenset()

# Flex containers of buttons that deliberately do not wrap. Empty, and meant to
# stay that way: a wrapped button row is never worse than an overflowing one.
KNOWN_NO_WRAP: frozenset[str] = frozenset()

# Fixed px floors above MIN_CONTENT_WIDTH. A floor wider than the content box
# cannot be satisfied, so the element overflows its parent no matter what the
# parent does. Only something inside its own scroll container belongs here.
KNOWN_WIDE_FLOORS = {
    ".table-container--wide > table",  # scrolls inside .table-container
}

_SELECTOR_GROUP = re.compile(
    r"^\s*(\.[A-Za-z0-9_.\-> ]*(?:actions|buttons|controls|toolbar)[A-Za-z0-9_\-]*)\s*\{([^}]*)\}",
    re.M,
)
_RULE = re.compile(r"^\s*([^@{}/][^{}]*?)\s*\{([^}]*)\}", re.M)
_FLOOR = re.compile(r"(?:min-width:\s*|minmax\(\s*)(\d+)px")


def _templates() -> list[Path]:
    """Every reflowing template — PDF templates render at a fixed paper width."""
    return [
        p
        for p in sorted(TEMPLATE_DIR.rglob("*.html"))
        if "_pdf" not in p.name and p.relative_to(TEMPLATE_DIR).as_posix() not in EXEMPT_TEMPLATES
    ]


def _tables(src: str):
    """Yield (line number, full ``<table>…</table>`` block, text before it)."""
    for match in re.finditer(r"<table\b.*?</table>", src, re.S):
        yield src[: match.start()].count("\n") + 1, match.group(0), src[: match.start()]


def _column_count(block: str) -> int:
    rows = re.findall(r"<tr\b.*?</tr>", block, re.S)
    return max((len(re.findall(r"<t[dh]\b", row)) for row in rows), default=0)


class ButtonGroupWrapTests(SimpleTestCase):
    """Failure mode 1: a flex button group that cannot wrap overflows its parent."""

    def test_flex_button_groups_declare_flex_wrap(self):
        css = CSS_PATH.read_text()
        offenders = [
            selector.strip()
            for match in _SELECTOR_GROUP.finditer(css)
            for selector, body in [(match.group(1), match.group(2))]
            if "display: flex" in body
            and "flex-wrap" not in body
            and selector.strip() not in KNOWN_NO_WRAP
        ]
        self.assertEqual(
            offenders,
            [],
            "Button groups are flex containers with no flex-wrap, so they size to "
            "max-content and run past their parent's edge once the window is "
            f"narrower than ~{MIN_SUPPORTED_VIEWPORT}px: {offenders}. Add "
            "'flex-wrap: wrap' — it changes nothing at full width.",
        )


class TableScrollContainerTests(SimpleTestCase):
    """Failure modes 2 and 3: tables that crush their columns instead of scrolling."""

    def test_every_table_sits_in_a_scroll_container(self):
        offenders = []
        for path in _templates():
            src = path.read_text()
            for line, _block, before in _tables(src):
                if not re.search(r'<div class="[^"]*\btable-container\b[^"]*"[^>]*>\s*$', before):
                    offenders.append(f"{path.relative_to(TEMPLATE_DIR).as_posix()}:{line}")
        self.assertEqual(
            offenders,
            [],
            'Tables are not wrapped in <div class="table-container">, so they '
            "crush their columns to fit instead of scrolling: "
            f"{offenders}. The container must be the table's immediate parent.",
        )

    def test_wide_tables_have_something_to_scroll_against(self):
        offenders = []
        for path in _templates():
            src = path.read_text()
            for line, block, before in _tables(src):
                columns = _column_count(block)
                if columns < WIDE_TABLE_COLUMNS:
                    continue
                container = re.search(
                    r'<div class="([^"]*\btable-container\b[^"]*)"[^>]*>\s*$', before
                )
                if container and "table-container--wide" in container.group(1):
                    continue
                offenders.append(
                    f"{path.relative_to(TEMPLATE_DIR).as_posix()}:{line} ({columns} columns)"
                )
        self.assertEqual(
            offenders,
            [],
            f"Tables with {WIDE_TABLE_COLUMNS}+ columns need "
            "'table-container table-container--wide' on the wrapper. The wrapper "
            "alone does nothing: .table-container table is width:100%, so the "
            "table never exceeds the container and overflow-x never triggers. "
            f"{offenders}",
        )


class FixedWidthFloorTests(SimpleTestCase):
    """A px floor wider than the content box overflows whatever contains it."""

    def test_no_fixed_floor_exceeds_the_minimum_content_width(self):
        css = CSS_PATH.read_text()
        offenders = []
        for match in _RULE.finditer(css):
            selector, body = match.group(1).strip(), match.group(2)
            if selector in KNOWN_WIDE_FLOORS or selector.startswith("@"):
                continue
            offenders.extend(
                f"{selector} ({value}px)"
                for value in _FLOOR.findall(body)
                if int(value) > MIN_CONTENT_WIDTH
            )
        self.assertEqual(
            offenders,
            [],
            f"Fixed px floors wider than the {MIN_CONTENT_WIDTH}px content box at "
            f"the {MIN_SUPPORTED_VIEWPORT}px minimum supported window — these "
            "overflow their parent regardless of what the parent does: "
            f"{offenders}. Use 'min(<n>px, 100%)' in the minmax()/min-width, or "
            "put the element in its own scroll container.",
        )
