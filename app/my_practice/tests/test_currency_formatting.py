"""Guardrail: money is formatted through utils.formatting, never by hand.

``f"{x:,.2f}".replace(",", ".")`` looks like German formatting and is not:
it turns 1,234.50 into "1.234.50 €" and leaves 80.00 as "80.00 €". That shipped
in the client-facing payment reminder email, beside invoice PDFs reading
"1.234,50 €", and in the bank-import invoice picker — while the correct helper,
format_currency_de (or the |currency filter in templates), already existed.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from ..utils.formatting import format_currency_de

APP_DIR = Path(settings.BASE_DIR) / "my_practice"
TEMPLATE_DIR = Path(settings.BASE_DIR) / "templates"
# `{{ x|floatformat:2 }} €` — no thousands separator, and English decimals in
# the English UI. The dashboard tiles read "32435 €" beside "12.930,00 €".
TEMPLATE_MONEY = re.compile(r"floatformat[^}]*\}\}(?:\s|&nbsp;)*€")
# A thousands-grouped format spec: the first half of the hand-rolled pattern.
GROUPED_FORMAT = re.compile(r":,\.\d+f\}")
ALLOWED = {"utils/formatting.py"}


class CurrencyFormattingTests(SimpleTestCase):
    def test_no_hand_rolled_thousands_formatting(self):
        offenders = []
        for path in sorted(APP_DIR.rglob("*.py")):
            rel = str(path.relative_to(APP_DIR)).replace("\\", "/")
            if rel.startswith("tests/") or rel in ALLOWED:
                continue
            for lineno, line in enumerate(path.read_text().splitlines(), start=1):
                if GROUPED_FORMAT.search(line):
                    offenders.append(f"{rel}:{lineno}")
        self.assertEqual(
            offenders, [], "Format money with format_currency_de (or |currency in templates)."
        )

    def test_templates_use_the_currency_filters_for_money(self):
        offenders = []
        for path in sorted(TEMPLATE_DIR.rglob("*.html")):
            source = path.read_text()
            for match in TEMPLATE_MONEY.finditer(source):
                line = source.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.relative_to(TEMPLATE_DIR)}:{line}")
        self.assertEqual(offenders, [], "Use |currency or |currency_rounded for amounts.")

    def test_helper_formats_the_german_way(self):
        self.assertEqual(format_currency_de("1234.5"), "1.234,50 €")
        self.assertEqual(format_currency_de(80), "80,00 €")
