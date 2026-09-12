#!/usr/bin/env python3
"""Fail if helpers deliberately duplicated between dev.py and prod.py diverge.

prod.py ships to self-hosters as a single stdlib-only file — `curl -O prod.py`
into an otherwise empty directory, where `setup` then fetches the compose file
— so it cannot import a shared module, and the only sharing direction that
would work (dev.py importing prod.py) means moving workstation concerns into
the file that has to stay minimal. The overlap does not justify that: of 67
top-level functions across the two scripts, exactly one is duplicated.

So the copies stay, and this keeps them honest. It is not a general
"these files look alike" check — every other similarity between them is either
a deliberate difference (see the note on `_is_metered_connection` in both) or
two different programs that happen to spell a command the same way.
"""

import ast
import difflib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Functions that must stay byte-identical in both files. Add one only when the
# copies genuinely have to agree — a difference should be a bug, not a decision.
DUPLICATED = ("_confirm_metered_download",)

FILES = ("dev.py", "prod.py")


def _function_source(path, name):
    """Source text of a top-level function, or None if it isn't there."""
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return None


def main():
    failures = []
    for name in DUPLICATED:
        sources = {filename: _function_source(ROOT / filename, name) for filename in FILES}
        missing = [filename for filename, src in sources.items() if src is None]
        if missing:
            failures.append(
                f"{name}() is listed as duplicated but missing from: {', '.join(missing)}\n"
                "  Either restore it, or drop it from DUPLICATED in this script."
            )
            continue
        first, second = FILES
        if sources[first] != sources[second]:
            diff = difflib.unified_diff(
                sources[first].splitlines(),
                sources[second].splitlines(),
                fromfile=f"{first}:{name}",
                tofile=f"{second}:{name}",
                lineterm="",
            )
            failures.append(
                f"{name}() differs between {first} and {second}.\n"
                "  It is duplicated on purpose (prod.py ships as a single file) and the\n"
                "  two copies must match. Apply the change to both, or — if they now\n"
                "  need to differ — say why in a comment and remove it from DUPLICATED.\n"
                + "\n".join(f"  {line}" for line in diff)
            )

    if failures:
        print("Duplicated helpers are out of sync:\n", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}\n", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
