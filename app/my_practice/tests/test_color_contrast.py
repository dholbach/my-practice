"""Guardrail: colour tokens meant to be read as text meet WCAG AA (4.5:1).

A Chromium audit of 15 pages found contrast failures on every one of them,
light mode worst: the brand/link colour #667eea read at 3.7:1 on white, the
secondary text colour #718096 at 3.3:1 on the header controls, and the solid
tag chips carried white text at 2.4-3.1:1. Each looks fine to whoever picked
it on a good screen, so it only shows up when measured.

This test resolves the tokens of both themes from tailwind.css (light @theme,
then the [data-theme="dark"] overrides) and checks every pair that is used as
text-on-background. It cannot see a hardcoded colour in a component rule —
that is what test_css_tokens.py's hex ratchet is for.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

CSS = (Path(settings.BASE_DIR) / "static" / "css" / "tailwind.css").read_text()
AA = 4.5

TEXT = ("text-primary", "text-secondary", "text-muted", "link")
SURFACES = (
    "surface",
    "bg-primary",
    "bg-secondary",
    "bg-muted",
    "toggle-bg",
    "dropdown-bg",
    "dropdown-hover",
    "input-bg",
)
WHITE_TEXT_FILLS = ("btn-primary", "btn-secondary", "primary")


def _tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"--color-([\w-]+):\s*(#[0-9a-fA-F]{6})\b", block))


def _themes() -> dict[str, dict[str, str]]:
    light = _tokens(CSS[CSS.index("@theme {") :])
    dark_block = CSS[CSS.index('[data-theme="dark"] {') :]
    dark_block = dark_block[: dark_block.index("\n}")]
    return {"light": light, "dark": {**light, **_tokens(dark_block)}}


def _luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _text_pairs(tokens: dict[str, str]) -> list[tuple[str, str]]:
    pairs = [(fg, bg) for fg in TEXT for bg in SURFACES]
    pairs += [(k, f"{k}-bg") for k in ("danger", "warning", "success", "info")]
    pairs += [
        (name.replace("-bg", "-text"), name)
        for name in tokens
        if re.fullmatch(r"(badge|status)-[\w]+-bg", name)
    ]
    return [(fg, bg) for fg, bg in pairs if fg in tokens and bg in tokens]


class ColorContrastTests(SimpleTestCase):
    def test_both_themes_resolve(self):
        themes = _themes()
        self.assertNotEqual(themes["light"]["surface"], themes["dark"]["surface"])

    def test_text_tokens_meet_aa_on_their_backgrounds(self):
        failures = []
        for theme, tokens in _themes().items():
            for fg, bg in _text_pairs(tokens):
                ratio = contrast(tokens[fg], tokens[bg])
                if ratio < AA:
                    failures.append(f"{theme}: --color-{fg} on --color-{bg} = {ratio:.2f}")
        self.assertEqual(failures, [])

    def test_white_text_fills_meet_aa(self):
        failures = [
            f"{theme}: white on --color-{fill} = {contrast('#ffffff', tokens[fill]):.2f}"
            for theme, tokens in _themes().items()
            for fill in (*WHITE_TEXT_FILLS, *(n for n in tokens if n.startswith("tag-")))
            if fill in tokens and contrast("#ffffff", tokens[fill]) < AA
        ]
        self.assertEqual(failures, [])

    def test_contrast_formula(self):
        self.assertAlmostEqual(contrast("#ffffff", "#000000"), 21.0, places=1)
        self.assertAlmostEqual(contrast("#667eea", "#ffffff"), 3.66, places=2)
