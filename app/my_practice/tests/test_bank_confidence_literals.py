"""Bank match confidences are written as ``BankTransaction.Confidence.X``, not as strings.

``BankTransaction.Confidence`` is a StrEnum, so ``"auto-expense"`` and
``Confidence.AUTO_EXPENSE`` compare and filter the same and a literal keeps working. That
is the trap: the hyphenated values are easy to mistype, a state added to the enum and
missed in a hand-written list fails silently, and the admin badge once showed four of the
nine states as "unmatched" because nothing tied it to the enum. About 30 literals had
collected in the import views and importer by the fourth refactoring review.

Same scan as ``test_invoice_status_literals``: a ``match_confidence=...`` /
``..._confidence__in=...`` keyword, a comparison against something named ``...confidence...``,
and an assignment to a name or attribute called ``...confidence...`` (tuple targets too).
Templates and tests are not scanned.

``KNOWN_CONFIDENCE_LITERALS`` is a ratchet: shrink it, never grow it to make new code pass.
"""

import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from ..models import BankTransaction

APP_DIR = Path(settings.BASE_DIR) / "my_practice"

# "path:function" of a literal that really is not a bank match confidence.
KNOWN_CONFIDENCE_LITERALS: set[str] = set()

CONFIDENCE_WORDS = {str(confidence) for confidence in BankTransaction.Confidence}


def _confidence_literals(node: ast.AST) -> list[ast.Constant]:
    """The constants in ``node`` (or in a list/tuple/set of them) that spell a confidence."""
    if isinstance(node, ast.Constant) and node.value in CONFIDENCE_WORDS:
        return [node]
    if isinstance(node, ast.List | ast.Tuple | ast.Set):
        return [found for element in node.elts for found in _confidence_literals(element)]
    return []


def _name_of(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _is_confidence_name(node: ast.AST) -> bool:
    return "confidence" in _name_of(node).lower()


def _mentions_confidence(node: ast.AST) -> bool:
    return any(_is_confidence_name(child) for child in ast.walk(node))


def _enclosing_functions(tree: ast.AST) -> dict[int, str]:
    """Line -> name of the function it sits in (module level: "<module>")."""
    names: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for line in range(node.lineno, (node.end_lineno or node.lineno) + 1):
                names[line] = node.name
    return names


def _assigned_values(node: ast.Assign) -> list[ast.AST]:
    """The value each confidence-named target receives, tuple unpacking included."""
    values = []
    for target in node.targets:
        if isinstance(target, ast.Tuple | ast.List) and isinstance(node.value, ast.Tuple):
            values += [
                value
                for leaf, value in zip(target.elts, node.value.elts, strict=False)
                if _is_confidence_name(leaf)
            ]
        elif _is_confidence_name(target):
            values.append(node.value)
    return values


def confidence_literals_in(source: str) -> list[tuple[int, str]]:
    """(line, word) of every bank match confidence written as a string in ``source``."""
    tree = ast.parse(source)
    found: list[ast.Constant] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg and "confidence" in node.arg:
            found += _confidence_literals(node.value)
        elif isinstance(node, ast.Compare):
            sides = [node.left, *node.comparators]
            if any(_mentions_confidence(side) for side in sides):
                for side in sides:
                    found += _confidence_literals(side)
        elif isinstance(node, ast.Assign):
            for value in _assigned_values(node):
                found += _confidence_literals(value)
    return sorted({(constant.lineno, constant.value) for constant in found})


class BankConfidenceLiteralTests(SimpleTestCase):
    def test_the_scan_finds_the_shapes_it_is_meant_to(self):
        source = "\n".join(
            [
                'BankTransaction.objects.filter(match_confidence="ignored")',
                'qs.filter(match_confidence__in=["exact", "fuzzy"])',
                'if trans.match_confidence == "manual": pass',
                'trans.match_confidence = "auto-expense"',
                'confidence = "auto-correction"',
                'confidence, notes = "unmatched", ""',
                'When(match_confidence="auto-withdrawal", then=1)',
            ]
        )
        self.assertEqual(
            sorted(word for _, word in confidence_literals_in(source)),
            sorted(
                [
                    "ignored",
                    "exact",
                    "fuzzy",
                    "manual",
                    "auto-expense",
                    "auto-correction",
                    "unmatched",
                    "auto-withdrawal",
                ]
            ),
        )

    def test_the_scan_leaves_other_strings_and_the_enum_alone(self):
        source = "\n".join(
            [
                "qs.filter(match_confidence=BankTransaction.Confidence.IGNORED)",
                'results["ignored"] += 1',
                'event.status = "ignored"',
                'label = "manual"',
                'if mode == "exact": pass',
                'notes, confidence = "exact", BankTransaction.Confidence.EXACT',
            ]
        )
        self.assertEqual(confidence_literals_in(source), [])

    def _scan(self) -> list[tuple[str, int, str, str]]:
        hits = []
        for path in sorted(APP_DIR.rglob("*.py")):
            rel = path.relative_to(APP_DIR).as_posix()
            if rel.startswith(("tests/", "migrations/")):
                continue
            source = path.read_text()
            functions = _enclosing_functions(ast.parse(source))
            for line, word in confidence_literals_in(source):
                hits.append((rel, line, word, functions.get(line, "<module>")))
        return hits

    def test_no_bank_confidence_is_written_as_a_string(self):
        offenders = [
            f"{rel}:{line} {word!r} in {function}"
            for rel, line, word, function in self._scan()
            if f"{rel}:{function}" not in KNOWN_CONFIDENCE_LITERALS
        ]
        self.assertEqual(
            offenders,
            [],
            "Write BankTransaction.Confidence.<NAME> instead of the string, so a renamed or "
            "added state is found by grep and a typo is an error.",
        )

    def test_allowlist_has_no_stale_entries(self):
        found = {f"{rel}:{function}" for rel, _, _, function in self._scan()}
        self.assertEqual(sorted(KNOWN_CONFIDENCE_LITERALS - found), [])
