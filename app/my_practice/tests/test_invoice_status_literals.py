"""Invoice statuses are written as ``Invoice.Status.X``, not as bare strings.

``Invoice.Status`` is a StrEnum, so ``"paid"`` and ``Invoice.Status.PAID`` compare and
filter the same, and a literal still works. That is the problem: a typo (``"canceled"``)
or a status added to the enum and missed in a hand-written list fails silently, and a
grep for where a status is used finds only some of the places. About 60 literals had
collected in ``revenue_helpers``, ``analytics_utils`` and the views by the third
refactoring review.

The scan reads the source with ``ast`` and looks for a status word in the three shapes
that matter: a ``status=...`` / ``..._status=...`` / ``status__in=...`` keyword, a
comparison against something named ``...status...``, and an assignment to ``.status``.
Templates and tests are not scanned (a test may spell out the string it expects).

``KNOWN_STATUS_LITERALS`` is a ratchet like the other guardrails: shrink it, never grow
it to make new code pass.
"""

import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from ..models import Invoice

APP_DIR = Path(settings.BASE_DIR) / "my_practice"

# "path:function" of a literal that really is not an Invoice status.
KNOWN_STATUS_LITERALS: set[str] = set()

STATUS_WORDS = {str(status) for status in Invoice.Status}


def _status_literals(node: ast.AST) -> list[ast.Constant]:
    """The constants in ``node`` (or in a list/tuple/set of them) that spell a status."""
    if isinstance(node, ast.Constant) and node.value in STATUS_WORDS:
        return [node]
    if isinstance(node, ast.List | ast.Tuple | ast.Set):
        return [found for element in node.elts for found in _status_literals(element)]
    return []


def _mentions_status(node: ast.AST) -> bool:
    return any(
        "status" in (child.attr if isinstance(child, ast.Attribute) else child.id).lower()
        for child in ast.walk(node)
        if isinstance(child, ast.Attribute | ast.Name)
    )


def _enclosing_functions(tree: ast.AST) -> dict[int, str]:
    """Line -> name of the function it sits in (module level: "<module>")."""
    names: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for line in range(node.lineno, (node.end_lineno or node.lineno) + 1):
                names[line] = node.name
    return names


def status_literals_in(source: str) -> list[tuple[int, str]]:
    """(line, word) of every invoice status written as a string in ``source``."""
    tree = ast.parse(source)
    found: list[ast.Constant] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg and "status" in node.arg:
            found += _status_literals(node.value)
        elif isinstance(node, ast.Compare):
            sides = [node.left, *node.comparators]
            if any(_mentions_status(side) for side in sides):
                for side in sides:
                    found += _status_literals(side)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Attribute) and target.attr == "status" for target in node.targets
        ):
            found += _status_literals(node.value)
    return sorted({(constant.lineno, constant.value) for constant in found})


class InvoiceStatusLiteralTests(SimpleTestCase):
    def test_the_scan_finds_the_shapes_it_is_meant_to(self):
        source = "\n".join(
            [
                'Invoice.objects.filter(status="paid")',
                'Invoice.objects.filter(invoice__status__in=["draft", "sent"])',
                'if invoice.status == "cancelled": pass',
                'if invoice.status in ("sent", "written_off"): pass',
                'invoice.status = "paid"',
                'When(status="draft", then=1)',
            ]
        )
        self.assertEqual(
            [word for _, word in status_literals_in(source)],
            ["paid", "draft", "sent", "cancelled", "sent", "written_off", "paid", "draft"],
        )

    def test_the_scan_leaves_other_strings_and_the_enum_alone(self):
        source = "\n".join(
            [
                "Invoice.objects.filter(status=Invoice.Status.PAID)",
                'event.status = "skipped"',
                'if inquiry.status == "new": pass',
                'label = "paid"',
                'if mode == "paid": pass',
                'Invoice.objects.filter(client__code="draft")',
            ]
        )
        self.assertEqual(status_literals_in(source), [])

    def test_no_invoice_status_is_written_as_a_string(self):
        offenders = []
        for path in sorted(APP_DIR.rglob("*.py")):
            rel = path.relative_to(APP_DIR).as_posix()
            if rel.startswith(("tests/", "migrations/")):
                continue
            source = path.read_text()
            functions = _enclosing_functions(ast.parse(source))
            for line, word in status_literals_in(source):
                function = functions.get(line, "<module>")
                if f"{rel}:{function}" not in KNOWN_STATUS_LITERALS:
                    offenders.append(f"{rel}:{line} {word!r} in {function}")
        self.assertEqual(
            offenders,
            [],
            "Write Invoice.Status.<NAME> instead of the string, so a renamed or added status "
            "is found by grep and a typo is an error.",
        )

    def test_allowlist_has_no_stale_entries(self):
        found = set()
        for path in sorted(APP_DIR.rglob("*.py")):
            rel = path.relative_to(APP_DIR).as_posix()
            if rel.startswith(("tests/", "migrations/")):
                continue
            source = path.read_text()
            functions = _enclosing_functions(ast.parse(source))
            found |= {
                f"{rel}:{functions.get(line, '<module>')}" for line, _ in status_literals_in(source)
            }
        self.assertEqual(sorted(KNOWN_STATUS_LITERALS - found), [])
