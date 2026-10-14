"""Guardrail: money is formatted through utils.formatting, never by hand.

``f"{x:,.2f}".replace(",", ".")`` looks like German formatting and is not:
it turns 1,234.50 into "1.234.50 €" and leaves 80.00 as "80.00 €". That shipped
in the client-facing payment reminder email, beside invoice PDFs reading
"1.234,50 €", and in the bank-import invoice picker — while the correct helper,
format_currency_de (or the |currency filter in templates), already existed.
"""

import re
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from ..templatetags.payment_tags import currency, currency_rounded
from ..utils.formatting import format_currency_de

APP_DIR = Path(settings.BASE_DIR) / "my_practice"
TEMPLATE_DIR = Path(settings.BASE_DIR) / "templates"
# `{{ x|floatformat:2 }} €` — no thousands separator, and English decimals in
# the English UI. The dashboard tiles read "32435 €" beside "12.930,00 €".
TEMPLATE_MONEY = re.compile(r"floatformat[^}]*\}\}(?:\s|&nbsp;)*€")
# The same inside {% blocktrans with x=y|floatformat:0 %}…{{ x }} €…: the
# capacity widget's "Revenue this month: 11065 € / 12000 €" hid from the above.
BLOCKTRANS = re.compile(r"\{%\s*blocktrans(?P<head>[^%]*)%\}(?P<body>.*?)\{%\s*endblocktrans", re.S)
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
            for match in BLOCKTRANS.finditer(source):
                if "floatformat" in match["head"] and "€" in match["body"]:
                    line = source.count("\n", 0, match.start()) + 1
                    offenders.append(f"{path.relative_to(TEMPLATE_DIR)}:{line}")
        self.assertEqual(offenders, [], "Use |currency or |currency_rounded for amounts.")

    def test_helper_formats_the_german_way(self):
        self.assertEqual(format_currency_de("1234.5"), "1.234,50 €")
        self.assertEqual(format_currency_de(80), "80,00 €")

    def test_amounts_round_half_up_like_on_paper(self):
        # float formatting rounded 2.675 (stored as 2.67499…) down, and round()
        # rounds halves to even: 2.5 -> 2, 11064.5 -> 11064.
        self.assertEqual(format_currency_de(Decimal("2.675")), "2,68 €")
        self.assertEqual(format_currency_de(2.675), "2,68 €")
        self.assertEqual(format_currency_de(Decimal("1234.565")), "1.234,57 €")
        self.assertEqual(format_currency_de(Decimal("2.5"), whole=True), "3 €")
        self.assertEqual(format_currency_de(Decimal("11064.50"), whole=True), "11.065 €")
        self.assertEqual(currency_rounded(Decimal("0.5")), "1 €")
        self.assertEqual(currency_rounded(Decimal("-2.5")), "-3 €")

    def test_filters_pass_non_numbers_through(self):
        self.assertEqual(currency("n/a"), "n/a")
        self.assertEqual(currency_rounded(""), "")
        self.assertEqual(currency(None), "–")
