"""An exception's text is not put into a message or response shown to the user.

``str(e)`` of an arbitrary exception can carry a host name, a file path, a SQL fragment or
the library's own wording. CodeQL flagged one (``py/stack-trace-exposure``) and a grep for
``str(e)`` then missed four more that passed ``e`` straight into the format arguments.
The scan reads the source with ``ast`` and looks, inside every ``except ... as name``
handler, for that name used in the arguments of a call that reaches the user:
``messages.*``, ``json_error``, ``JsonResponse``, ``HttpResponse*``, ``add_error`` and
``errors.append``. Logging calls and ``raise ... from name`` are fine.

What it cannot see: the text copied into a variable first (``msg = str(e)``) and the
variable passed on, and a message built in a helper the handler calls.

``KNOWN_EXCEPTION_TEXT`` lists handlers whose exception is a validation error written for
the user. It is a ratchet like the other guardrails: shrink it, never grow it to make new
code pass.
"""

import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

APP_DIR = Path(settings.BASE_DIR) / "my_practice"

# "path:function:ExceptionType" of a handler whose exception text is meant for the user.
KNOWN_EXCEPTION_TEXT: set[str] = {
    # process_upload raises ValueError with a message about the file (type, size).
    "views/client_views.py:client_document_upload:ValueError",
    "views/expense_views.py:form_valid:ValueError",
    # A model's save-time ValidationError is written for the user.
    "views/invoice_views.py:form_valid:ValidationError",
}

SINK_NAMES = {"json_error", "JsonResponse", "add_error"}
SINK_PREFIXES = ("HttpResponse",)


def _call_name(call: ast.Call) -> tuple[str, str]:
    """(object, name) of the callee: ``messages.error`` -> ("messages", "error")."""
    func = call.func
    if isinstance(func, ast.Attribute):
        owner = func.value.id if isinstance(func.value, ast.Name) else ""
        return owner, func.attr
    if isinstance(func, ast.Name):
        return "", func.id
    return "", ""


def _is_sink(call: ast.Call) -> bool:
    owner, name = _call_name(call)
    return (
        owner == "messages"
        or name in SINK_NAMES
        or name.startswith(SINK_PREFIXES)
        or (owner == "errors" and name == "append")
    )


def _uses(node: ast.AST, name: str) -> bool:
    return any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node))


def exception_text_sinks_in(source: str) -> list[tuple[int, str]]:
    """(line, "function:ExceptionType") of every call that puts a caught exception in a message."""
    tree = ast.parse(source)
    found: set[tuple[int, str]] = set()

    def visit(node: ast.AST, function: str) -> None:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            function = node.name
        if isinstance(node, ast.ExceptHandler) and node.name:
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and _is_sink(child):
                    arguments = [*child.args, *(keyword.value for keyword in child.keywords)]
                    if any(_uses(argument, node.name) for argument in arguments):
                        caught = ast.unparse(node.type) if node.type else "BaseException"
                        found.add((child.lineno, f"{function}:{caught}"))
        for child in ast.iter_child_nodes(node):
            visit(child, function)

    visit(tree, "<module>")
    return sorted(found)


class ExceptionTextTests(SimpleTestCase):
    def test_the_scan_finds_the_shapes_it_is_meant_to(self):
        source = "\n".join(
            [
                "def a(request):",
                "    try: pass",
                "    except Exception as e:",
                '        messages.error(request, _("x: %(error)s") % {"error": str(e)})',
                "def b(request):",
                "    try: pass",
                "    except Exception as exc:",
                "        return json_error(exc)",
                "def c(request):",
                "    try: pass",
                "    except Exception as e:",
                '        errors.append(_("x: %(error)s") % {"error": e})',
                "def d(request):",
                "    try: pass",
                "    except ValueError as e:",
                "        return JsonResponse({'error': str(e)})",
            ]
        )
        self.assertEqual(
            [function for _, function in exception_text_sinks_in(source)],
            ["a:Exception", "b:Exception", "c:Exception", "d:ValueError"],
        )

    def test_the_scan_leaves_logging_and_other_calls_alone(self):
        source = "\n".join(
            [
                "def a(request):",
                "    try: pass",
                "    except Exception as e:",
                '        logger.exception("failed: %s", e)',
                '        messages.error(request, _("Something failed."))',
                "        raise RuntimeError('x') from e",
                "def b(request):",
                "    try: pass",
                "    except Exception:",
                '        messages.error(request, str("e"))',
                "def c(request, e):",
                "    messages.error(request, str(e))",
            ]
        )
        self.assertEqual(exception_text_sinks_in(source), [])

    def _scan(self) -> list[tuple[str, int, str]]:
        hits = []
        for path in sorted(APP_DIR.rglob("*.py")):
            rel = path.relative_to(APP_DIR).as_posix()
            if rel.startswith(("tests/", "migrations/")):
                continue
            hits += [
                (rel, line, function)
                for line, function in exception_text_sinks_in(path.read_text())
            ]
        return hits

    def test_no_exception_text_reaches_the_user(self):
        offenders = [
            f"{rel}:{line} in {function}"
            for rel, line, function in self._scan()
            if f"{rel}:{function}" not in KNOWN_EXCEPTION_TEXT
        ]
        self.assertEqual(
            offenders,
            [],
            "Log the exception (logger.exception) and show a fixed message, like "
            '"... Details are in the server log."',
        )

    def test_allowlist_has_no_stale_entries(self):
        found = {f"{rel}:{function}" for rel, _, function in self._scan()}
        self.assertEqual(sorted(KNOWN_EXCEPTION_TEXT - found), [])
