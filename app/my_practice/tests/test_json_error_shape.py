"""AJAX endpoints answer errors with ``json_error``, never a hand-built ``{"error": ...}``.

Page scripts read one shape, ``{"success": false, "error": message}``. A view that wrote
``JsonResponse({"error": ...})` itself omitted ``success``, and the next script written
against that endpoint had to special-case it. The scan reads the source with ``ast`` and
flags a ``JsonResponse`` whose dict literal has an ``"error"`` key.

What it cannot see: a dict built in a variable first, and an error returned through a
different response class.
"""

import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

VIEWS_DIR = Path(settings.BASE_DIR) / "my_practice" / "views"


def _hand_built_errors(tree: ast.AST) -> list[int]:
    """Line numbers of ``JsonResponse({... "error": ...})`` calls."""
    lines = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "JsonResponse"
            and node.args
            and isinstance(node.args[0], ast.Dict)
        ):
            continue
        keys = {k.value for k in node.args[0].keys if isinstance(k, ast.Constant)}
        if "error" in keys:
            lines.append(node.lineno)
    return lines


class JsonErrorShapeTests(SimpleTestCase):
    def test_views_use_json_error(self):
        offenders = []
        for path in sorted(VIEWS_DIR.glob("*.py")):
            offenders.extend(
                f"views/{path.name}:{line}"
                for line in _hand_built_errors(ast.parse(path.read_text()))
            )
        self.assertFalse(
            offenders,
            "Use json_error(message, status) from utils.view_helpers instead of "
            "JsonResponse({'error': ...}):\n  " + "\n  ".join(offenders),
        )

    def test_the_scan_sees_a_hand_built_error(self):
        tree = ast.parse('JsonResponse({"error": "x"}, status=400)\nJsonResponse({"saved": True})')
        self.assertEqual(_hand_built_errors(tree), [1])
