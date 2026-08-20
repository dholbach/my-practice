"""Guardrails for the CSS token system (M-PAT-04).

Two failure modes that are invisible in review and in light mode, both of which
had live instances when this test was added:

1. ``var(--token)`` where the token is never defined. With no fallback the whole
   declaration is dropped (invalid at computed-value time), so the property
   silently reverts to inherited/initial — a background or hover highlight just
   doesn't render. With a hardcoded fallback the fallback wins permanently,
   which defeats the point of the token and breaks dark mode.

2. Hardcoded hex on a *semantic* component class. ``--color-*`` tokens flip
   between light and dark via ``[data-theme="dark"]``; a literal hex does not, so
   a light background ends up carrying the dark theme's near-white text. That is
   how the triage card and the onboarding step ended up with invisible text.

Both lists are ratchets: shrink them, never grow them.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

CSS_PATH = Path(settings.BASE_DIR) / "static" / "css" / "tailwind.css"

# Tokens referenced with a deliberate non-token fallback chain, where the
# fallback is itself a real token — harmless, and clearer than restating it.
ALLOWED_UNDEFINED_TOKENS = {
    "--card-bg",  # var(--card-bg, var(--color-bg-secondary))
    "--bg-hover",  # var(--bg-hover, var(--color-bg-primary))
    "--color-primary-soft",  # var(--color-primary-soft, color-mix(...))
    "--year-text",  # set per .year-<n> rule, with a #fff fallback
}

# Rules still carrying literal hex. Everything here renders the same in both
# themes; entries are fine only while that is intentional (brand gradients,
# fixed-palette swatches, coloured buttons with white text). Do not add to this
# list to make a new hardcoded colour pass — use a --color-* token instead.
KNOWN_HARDCODED_HEX_PREFIXES = (
    ".stat-card",  # brand gradient headers
    ".color-box",  # the tag colour picker's fixed swatch palette
    ".year-",  # per-year chart palette
    ".heatmap-cell",  # activity gradient, deliberately light in both themes
    ".todo-badge",  # category/priority palette
    ".billing-summary__chip",
    ".cn-session-",
    ".btn-",  # coloured action buttons (white on brand colour)
    ".btn.btn-",  # …and the compound forms that have to outrank .btn itself
    ".badge--",
    ".audit-",
    ".month-bar",
    ".seasonality-bar",
    ".capacity-fill",
    ".insights-section",
    ".legend-",
    ".timeoff-table__",
    ".progress-bar-fill",
    ".chart-bar",
    ".monthly-bar",
    ".summary-table",
    ".summary-cards",
    ".tax-summary-container",
    ".checklist-",
    ".message.",
    ".text-muted-light",
    ".tag-add-btn",
    ".tag-dropdown-item",
    ".bank-import-status__btn",
    ".bank-tx-",
    ".receipt-delete-btn",
    ".expenses-container",
    ".client-card",
    ".last-invoice",
    ".client-workflow-stats",
    ".weekly-focus-task",
    ".todo-item",
    ".todo-due-date",
    ".status-card",
    ".placeholder-warning",
    ".step-",
    ".cockpit-",
    ".onboarding-step",
    ".errorlist",  # Django-rendered; see note in the stylesheet
    ".stat-hint",
    ".row-",
    ".dropzone-",
    ".action-btn",
    ".cn-needs-log",
    ".cn-status-badge",
    ".col-",
    ".alert-",
    "code",
)

TOKEN_DEF = re.compile(r"(--[\w-]+)\s*:")
TOKEN_USE = re.compile(r"var\(\s*(--[\w-]+)\s*(,)?")
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def _css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


class CssTokenDefinitionTests(SimpleTestCase):
    def test_every_referenced_token_is_defined(self):
        """var(--x) must resolve, or the declaration is silently dropped."""
        css = _css()
        defined = set(TOKEN_DEF.findall(css))
        undefined = {
            name
            for name, _fallback in TOKEN_USE.findall(css)
            if name not in defined and name not in ALLOWED_UNDEFINED_TOKENS
        }
        self.assertEqual(
            undefined,
            set(),
            "CSS custom properties referenced but never defined — the declaration "
            "is dropped and the property falls back to inherited/initial. Define "
            "the token, or use an existing --color-* one:\n  " + "\n  ".join(sorted(undefined)),
        )

    def test_allowlisted_undefined_tokens_are_still_referenced(self):
        """Keeps ALLOWED_UNDEFINED_TOKENS from going stale."""
        css = _css()
        referenced = {name for name, _ in TOKEN_USE.findall(css)}
        stale = ALLOWED_UNDEFINED_TOKENS - referenced
        self.assertEqual(
            stale,
            set(),
            f"No longer referenced — drop from ALLOWED_UNDEFINED_TOKENS: {sorted(stale)}",
        )


class CssHardcodedColourTests(SimpleTestCase):
    def test_no_new_hardcoded_hex_on_component_classes(self):
        """Hardcoded hex doesn't flip with the theme; --color-* tokens do."""
        offenders = []
        in_token_block = False

        for lineno, line in enumerate(_css().splitlines(), 1):
            stripped = line.strip()
            if re.match(r"@theme\b|:root|\[data-theme", stripped):
                in_token_block = True
            if in_token_block:
                if stripped.startswith("}"):
                    in_token_block = False
                continue
            if "{" not in stripped or stripped.startswith(("--", "/*", "*", "@")):
                continue
            if not HEX.search(stripped.split("{", 1)[1]):
                continue

            selector = stripped.split("{", 1)[0].strip()
            if selector.startswith(KNOWN_HARDCODED_HEX_PREFIXES):
                continue
            offenders.append(f"{lineno}: {selector}")

        self.assertEqual(
            offenders,
            [],
            "Hardcoded hex outside the token blocks. These do not adapt to dark "
            "mode — use a --color-* token (see CLAUDE.md, CSS Architecture):\n  "
            + "\n  ".join(offenders),
        )
