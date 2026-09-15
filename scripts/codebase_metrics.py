#!/usr/bin/env python3
"""
Track how the codebase grows and what kind of work goes into it.

Rebuilds a month-by-month history straight from git — lines of code per
category, conventional-commit mix, releases — and renders it to
docs/development/. The point is to make two things visible that are easy to
lose track of on a long-running solo project:

  * whether feature work is still happening, or has quietly been replaced by
    maintenance (the commit mix), and
  * which part of the repo is actually growing (app code vs. tests vs. docs vs.
    migrations), since "the repo feels big" and "the app got bigger" are very
    different problems with different fixes.

Everything is recomputed from scratch on every run rather than appended to, so
the output is idempotent and self-healing: a rewritten history, a corrected
commit message or a new category definition all just show up on the next run.
There is no state to drift.

Outputs:
    docs/development/metrics.json   raw series, diffable, the source of truth
    docs/development/README.md      rendered tables + charts

Usage:
    scripts/codebase_metrics.py           # regenerate both files
    scripts/codebase_metrics.py --check   # exit 1 if regeneration would change
                                          # them (for CI / pre-release checks)
    scripts/codebase_metrics.py --stdout  # print the README instead of writing
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "docs" / "development"
JSON_PATH = OUT_DIR / "metrics.json"
README_PATH = OUT_DIR / "README.md"

# Line-count categories, each a git pathspec list. Order is display order.
#
# Plain `*` in a git pathspec matches `/` too (it is fnmatch without
# FNM_PATHNAME), so `app/my_practice/*.py` reaches nested packages like
# admin/ and views/ without needing `**` or :(glob) magic.
#
# The split exists to answer "what is growing?". Lumping these together is what
# makes a repo feel like it is sprawling when in fact only the test suite grew:
# app code is surface area you have to hold in your head, tests are insurance,
# migrations are pure accumulation, and docs should stay roughly flat.
CATEGORIES = {
    "app": [
        "app/my_practice/*.py",
        ":(exclude)app/my_practice/tests/*",
        ":(exclude)app/my_practice/migrations/*",
    ],
    "tests": [
        "app/my_practice/tests/*.py",
        "app/static/js/*.test.js",
        "app/static/js/tests/*.js",
    ],
    "templates": ["app/templates/*.html"],
    "js": [
        "app/static/js/*.js",
        ":(exclude)app/static/js/*.test.js",
        ":(exclude)app/static/js/tests/*",
        ":(exclude)*node_modules*",
    ],
    "css": ["app/static/css/tailwind.css"],
    "migrations": ["app/my_practice/migrations/*.py"],
    "docs": ["*.md", ":(exclude)*node_modules*"],
}

# Conventional-commit types worth reporting separately. Anything else that
# parses as `type:` lands in "other"; anything unparseable is ignored rather
# than guessed at.
COMMIT_TYPES = ["feat", "fix", "refactor", "perf", "test", "docs", "chore", "ci", "style"]

# feat/fix/refactor/perf touch the product or its structure; the rest keep the
# lights on. Used for the single headline "product work" percentage.
PRODUCT_TYPES = {"feat", "fix", "refactor", "perf"}

SUBJECT_RE = re.compile(r"^([a-z]+)(?:\([^)]*\))?!?:", re.IGNORECASE)


def git(*args: str) -> str:
    """Run a git command in the repo and return stdout, or "" if it found nothing.

    git grep and git rev-list both exit 1 on "no matches", which is a normal
    answer here (a category with no files yet in an early month), not an error.
    """
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def month_range() -> list[str]:
    """Every YYYY-MM from the first commit to the current month, inclusive."""
    first = git("log", "--reverse", "--format=%ad", "--date=short").splitlines()[0]
    start = datetime.strptime(first, "%Y-%m-%d").date().replace(day=1)
    today = datetime.now(timezone.utc).date()
    months, cursor = [], start
    while cursor <= today.replace(day=1):
        months.append(cursor.strftime("%Y-%m"))
        cursor = (cursor.replace(day=28) + timedelta(days=7)).replace(day=1)
    return months


def month_bounds(month: str) -> tuple[str, str]:
    """ISO start and exclusive-end timestamps for a YYYY-MM string."""
    year, mon = (int(p) for p in month.split("-"))
    start = date(year, mon, 1)
    end = date(year + (mon == 12), (mon % 12) + 1, 1)
    return start.isoformat(), end.isoformat()


def commit_at_month_end(month: str) -> str:
    """Last commit on or before the end of `month` (empty if the repo is younger)."""
    _, end = month_bounds(month)
    return git("rev-list", "-n1", f"--before={end}", "HEAD").strip()


def count_lines(rev: str, pathspec: list[str]) -> int:
    """Total lines across every file matching `pathspec` at `rev`.

    `git grep -c ''` matches every line of every tracked text file and prints
    `rev:path:count`, which is orders of magnitude faster than checking out or
    `git show`-ing each file — the whole history sweep runs in well under a
    second. Binary files are skipped automatically, which is what we want.
    """
    out = git("grep", "-c", "", rev, "--", *pathspec)
    return sum(int(line.rsplit(":", 1)[1]) for line in out.splitlines() if ":" in line)


def collect() -> dict:
    tags_by_month: dict[str, list[str]] = {}
    tag_lines = git(
        "for-each-ref",
        "--sort=creatordate",
        "--format=%(creatordate:short)|%(refname:short)",
        "refs/tags",
    )
    for line in tag_lines.splitlines():
        when, _, name = line.partition("|")
        tags_by_month.setdefault(when[:7], []).append(name)

    months = []
    for month in month_range():
        start, end = month_bounds(month)
        rev = commit_at_month_end(month)

        # --no-merges: this repo merges every PR, so merge commits would swamp
        # the mix and say nothing about what the work actually was.
        subjects = git(
            "log", "--no-merges", f"--since={start}", f"--until={end}", "--format=%s"
        ).splitlines()

        counts = dict.fromkeys(COMMIT_TYPES, 0)
        counts["other"] = 0
        parsed = 0
        for subject in subjects:
            match = SUBJECT_RE.match(subject)
            if not match:
                continue
            parsed += 1
            kind = match.group(1).lower()
            counts[kind if kind in counts else "other"] += 1

        months.append(
            {
                "month": month,
                "commits": len(subjects),
                "classified": parsed,
                "types": counts,
                # Already in creatordate order from for-each-ref. Sorting here
                # would be a string sort, which puts v0.2.10 before v0.2.7.
                "releases": tags_by_month.get(month, []),
                "loc": {
                    name: count_lines(rev, spec) if rev else 0 for name, spec in CATEGORIES.items()
                },
            }
        )

    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "head": git("rev-parse", "--short", "HEAD").strip(),
        "months": months,
    }


def bar(value: float, peak: float, width: int = 18) -> str:
    """Proportional block bar. Renders identically everywhere, unlike a chart."""
    if peak <= 0:
        return ""
    filled = round(value / peak * width)
    return "█" * filled if filled else ("▏" if value else "")


def delta(series: list[int]) -> str:
    """Percentage change across the whole series, formatted for a table cell."""
    first = next((v for v in series if v), 0)
    if not first:
        return "—"
    change = (series[-1] - first) / first * 100
    return f"{change:+.0f}%"


def xychart(title: str, months: list[str], axis: str, series: list[list[int]], kind: str) -> str:
    """A Mermaid xychart-beta block; GitHub renders these natively in Markdown."""
    peak = max((v for s in series for v in s), default=0)
    top = max(int(peak * 1.15), 1)
    labels = ", ".join(f'"{m}"' for m in months)
    lines = [
        "```mermaid",
        "xychart-beta",
        f'    title "{title}"',
        f"    x-axis [{labels}]",
        f'    y-axis "{axis}" 0 --> {top}',
    ]
    lines += [f"    {kind} [{', '.join(str(v) for v in s)}]" for s in series]
    lines.append("```")
    return "\n".join(lines)


def render(data: dict) -> str:
    months = data["months"]
    labels = [m["month"] for m in months]
    latest = months[-1]

    def loc(name: str) -> list[int]:
        return [m["loc"][name] for m in months]

    app, tests = loc("app"), loc("tests")
    feats = [m["types"]["feat"] for m in months]
    ratio = tests[-1] / app[-1] if app[-1] else 0
    total = sum(latest["loc"].values())

    out: list[str] = []
    add = out.append

    add("# Codebase development metrics")
    add("")
    add(
        "Generated by [`scripts/codebase_metrics.py`](../../scripts/codebase_metrics.py) — "
        "do not edit by hand. Refresh with `scripts/codebase_metrics.py`; a scheduled "
        "workflow also opens a refresh branch on the first of each month."
    )
    add("")
    add(f"**Snapshot — {data['generated']} (`{data['head']}`)**")
    add("")
    add("| | |")
    add("| --- | --- |")
    add(f"| Tracked lines | {total:,} |")
    add(f"| App code | {app[-1]:,} |")
    add(f"| Test code | {tests[-1]:,} |")
    add(f"| Test-to-code ratio | {ratio:.2f} : 1 |")
    add(f"| Releases so far | {sum(len(m['releases']) for m in months)} |")
    add("")
    add("## Is feature work still happening?")
    add("")
    add(
        "The first question to ask a maturing project. A long run of near-zero "
        "`feat:` months means maintenance has quietly become the whole job — "
        "fine if chosen, worth noticing if not."
    )
    add("")
    add(xychart("feat: commits per month", labels, "commits", [feats], "bar"))
    add("")
    add("## What is actually growing?")
    add("")
    add(
        "App code is surface area you have to hold in your head; tests are "
        "insurance. They grow for different reasons and only one of them is a "
        "warning sign."
    )
    add("")
    add(
        f"Mermaid draws these without a legend, so: app code is the series "
        f"ending at {app[-1]:,} lines, test code the one ending at "
        f"{tests[-1]:,}."
    )
    add("")
    add(xychart("App code vs. test code (lines)", labels, "lines", [app, tests], "line"))
    add("")
    add("### Lines by category")
    add("")
    header = "| Category | " + " | ".join(labels) + " | Change |"
    add(header)
    add("| --- |" + " ---: |" * (len(labels) + 1))
    for name in CATEGORIES:
        series = loc(name)
        cells = " | ".join(f"{v:,}" for v in series)
        add(f"| {name} | {cells} | {delta(series)} |")
    add("")
    add("## Where does the effort go?")
    add("")
    add(
        "Share of classified (non-merge, conventional-commit) work per month. "
        "`feat`/`fix`/`refactor`/`perf` move the product or its structure; the "
        "rest keep the lights on."
    )
    add("")
    add("| Month | Commits | Product work | Mix |")
    add("| --- | ---: | ---: | --- |")
    for m in months:
        classified = m["classified"]
        product = sum(m["types"][t] for t in PRODUCT_TYPES)
        share = product / classified * 100 if classified else 0
        add(f"| {m['month']} | {m['commits']} | {share:.0f}% | {bar(share, 100)} |")
    add("")
    add("### Commits by type")
    add("")
    add("| Type | " + " | ".join(labels) + " |")
    add("| --- |" + " ---: |" * len(labels))
    for kind in [*COMMIT_TYPES, "other"]:
        series = [m["types"][kind] for m in months]
        if not any(series):
            continue
        add(f"| {kind} | " + " | ".join(str(v) for v in series) + " |")
    add("")
    add("## Releases")
    add("")
    add("| Month | Count | Tags |")
    add("| --- | ---: | --- |")
    for m in months:
        names = ", ".join(f"`{t}`" for t in m["releases"]) or "—"
        add(f"| {m['month']} | {len(m['releases'])} | {names} |")
    add("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if output is stale")
    parser.add_argument("--stdout", action="store_true", help="print README instead of writing")
    args = parser.parse_args()

    data = collect()
    readme = render(data)
    payload = json.dumps(data, indent=2, sort_keys=True) + "\n"

    if args.stdout:
        print(readme)
        return 0

    if args.check:
        stale = [
            path.name
            for path, want in ((JSON_PATH, payload), (README_PATH, readme))
            if not path.is_file() or path.read_text(encoding="utf-8") != want
        ]
        if stale:
            print("Stale metrics output: " + ", ".join(stale), file=sys.stderr)
            print("Run scripts/codebase_metrics.py to refresh.", file=sys.stderr)
            return 1
        print("Metrics output is current.")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(payload, encoding="utf-8")
    README_PATH.write_text(readme, encoding="utf-8")
    print(f"Wrote {JSON_PATH.relative_to(REPO_ROOT)} and {README_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
