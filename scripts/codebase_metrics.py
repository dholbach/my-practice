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
    # docs/development is excluded on purpose: it is generated, and this page
    # is itself Markdown, so counting it made the docs figure drift by its own
    # size on every refresh.
    "docs": ["*.md", ":(exclude)*node_modules*", ":(exclude)docs/development/*"],
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


# One colour per category, reused by every chart so a category keeps its colour
# across the page. Chosen from GitHub's own palette: saturated enough to stay
# legible on a white background, light enough to stay legible on a dark one.
# `docs` deliberately is not grey — grey is the axis colour.
# Hues are assigned with the absolute chart in mind: templates and docs sit in
# the same band there, as do js and css, so each of those pairs is given
# maximally separated hues rather than neighbouring ones.
PALETTE = {
    "app": "#58a6ff",  # blue
    "tests": "#3fb950",  # green
    "templates": "#d29922",  # amber
    "js": "#a371f7",  # purple
    "css": "#39c5cf",  # cyan
    "migrations": "#db6d28",  # orange
    "docs": "#ff7b72",  # salmon
}
INK = "#8b949e"  # axes, gridlines and labels; readable on light and dark alike

# Chart geometry, in SVG user units.
WIDTH, HEIGHT = 840, 400
PAD_L, PAD_R, PAD_T, PAD_B = 76, 168, 46, 50
PLOT_W = WIDTH - PAD_L - PAD_R
PLOT_H = HEIGHT - PAD_T - PAD_B


def esc(text: str) -> str:
    """Minimal XML escaping for text nodes and attribute values."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def nice_max(peak: float) -> int:
    """Round an axis maximum up to a readable round number."""
    if peak <= 0:
        return 1
    step = 10 ** (len(str(int(peak))) - 1)
    for multiple in (1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10):
        top = step * multiple
        if top >= peak:
            return int(top)
    return int(step * 10)


def svg_chart(
    title: str,
    months: list[str],
    series: list[tuple[str, str, list[float]]],
    y_label: str,
    kind: str = "line",
    baseline: float | None = None,
) -> str:
    """Render a line or bar chart as a standalone SVG, with a real legend.

    Written by hand rather than with Mermaid because Mermaid's xychart-beta has
    no legend: every series is drawn in a palette colour that nothing on the
    page names, so a reader cannot tell which line is which. That is fine for
    one series and useless for seven, which is why "lines by category" was a
    table only.

    The output deliberately uses presentation attributes and no <style>, <script>
    or external references. GitHub serves an SVG referenced from Markdown through
    an <img>, and sanitises anything richer — this stays inside what survives.
    The background is transparent and every ink colour is mid-tone, so one file
    works in both GitHub themes without needing a <picture> element and two
    renders.
    """
    values = [v for _, _, vs in series for v in vs]
    top = nice_max(max(values, default=0))
    n = len(months)

    def x_at(i: int) -> float:
        # Bars are centred in a band so the first one does not straddle the
        # y-axis and collide with its "0" label; lines span edge to edge so the
        # series fills the full plot width.
        if kind == "bar":
            return PAD_L + (i + 0.5) * PLOT_W / max(n, 1)
        if n == 1:
            return PAD_L + PLOT_W / 2
        return PAD_L + i * PLOT_W / (n - 1)

    def y_at(v: float) -> float:
        return PAD_T + PLOT_H * (1 - v / top)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{esc(title)}">',
        f"<title>{esc(title)}</title>",
        f'<text x="{PAD_L}" y="26" font-family="sans-serif" font-size="15" '
        f'font-weight="600" fill="{INK}">{esc(title)}</text>',
    ]

    # Horizontal gridlines and their y-axis labels.
    for tick in range(6):
        v = top * tick / 5
        y = y_at(v)
        out.append(
            f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L + PLOT_W}" y2="{y:.1f}" '
            f'stroke="{INK}" stroke-opacity="0.22" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{PAD_L - 10}" y="{y + 4:.1f}" font-family="sans-serif" '
            f'font-size="11" fill="{INK}" text-anchor="end">{v:,.0f}</text>'
        )

    # A dashed rule at the index baseline, so "no growth" is visible at a glance.
    if baseline is not None and baseline <= top:
        y = y_at(baseline)
        out.append(
            f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L + PLOT_W}" y2="{y:.1f}" '
            f'stroke="{INK}" stroke-width="1" stroke-dasharray="4 3" stroke-opacity="0.7"/>'
        )

    out.append(
        f'<text x="16" y="{PAD_T + PLOT_H / 2:.1f}" font-family="sans-serif" font-size="11" '
        f'fill="{INK}" text-anchor="middle" '
        f'transform="rotate(-90 16 {PAD_T + PLOT_H / 2:.1f})">{esc(y_label)}</text>'
    )

    # X-axis labels.
    for i, month in enumerate(months):
        out.append(
            f'<text x="{x_at(i):.1f}" y="{PAD_T + PLOT_H + 20:.1f}" font-family="sans-serif" '
            f'font-size="11" fill="{INK}" text-anchor="middle">{esc(month)}</text>'
        )

    if kind == "bar":
        band = PLOT_W / max(n, 1)
        width = min(band * 0.45, 46)
        for _, colour, vs in series:
            for i, v in enumerate(vs):
                y = y_at(v)
                out.append(
                    f'<rect x="{x_at(i) - width / 2:.1f}" y="{y:.1f}" width="{width:.1f}" '
                    f'height="{PAD_T + PLOT_H - y:.1f}" fill="{colour}" rx="2"/>'
                )
                out.append(
                    f'<text x="{x_at(i):.1f}" y="{y - 7:.1f}" font-family="sans-serif" '
                    f'font-size="11" fill="{INK}" text-anchor="middle">{v:,.0f}</text>'
                )
    else:
        for _, colour, vs in series:
            points = " ".join(f"{x_at(i):.1f},{y_at(v):.1f}" for i, v in enumerate(vs))
            out.append(
                f'<polyline points="{points}" fill="none" stroke="{colour}" '
                f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
            )
            for i, v in enumerate(vs):
                out.append(f'<circle cx="{x_at(i):.1f}" cy="{y_at(v):.1f}" r="3" fill="{colour}"/>')

    # Legend — the whole reason this is hand-rolled SVG rather than Mermaid.
    legend_x = PAD_L + PLOT_W + 22
    for row, (label, colour, vs) in enumerate(series):
        y = PAD_T + 6 + row * 30
        out.append(
            f'<rect x="{legend_x}" y="{y - 7}" width="14" height="4" rx="2" fill="{colour}"/>'
        )
        out.append(
            f'<text x="{legend_x + 22}" y="{y}" font-family="sans-serif" font-size="12" '
            f'fill="{INK}">{esc(label)}</text>'
        )
        out.append(
            f'<text x="{legend_x + 22}" y="{y + 15}" font-family="sans-serif" font-size="10" '
            f'fill="{INK}" fill-opacity="0.75">{vs[-1]:,.0f}</text>'
        )

    out.append("</svg>")
    return "\n".join(out) + "\n"


def build(data: dict) -> dict[str, str]:
    """Produce every output file as {relative filename: content}."""
    months = data["months"]
    labels = [m["month"] for m in months]
    latest = months[-1]

    def loc(name: str) -> list[int]:
        return [m["loc"][name] for m in months]

    app, tests = loc("app"), loc("tests")
    feats = [m["types"]["feat"] for m in months]
    ratio = tests[-1] / app[-1] if app[-1] else 0
    total = sum(latest["loc"].values())

    files = {
        "chart-feature-commits.svg": svg_chart(
            "feat: commits per month",
            labels,
            [("feat", PALETTE["app"], [float(v) for v in feats])],
            "commits",
            kind="bar",
        ),
        "chart-app-vs-tests.svg": svg_chart(
            "App code vs. test code",
            labels,
            [
                ("app", PALETTE["app"], [float(v) for v in app]),
                ("tests", PALETTE["tests"], [float(v) for v in tests]),
            ],
            "lines",
        ),
        "chart-lines-by-category.svg": svg_chart(
            "Lines by category",
            labels,
            [(name, PALETTE[name], [float(v) for v in loc(name)]) for name in CATEGORIES],
            "lines",
        ),
        # Indexed to the first tracked month. The absolute chart above answers
        # "how big is each part?" but squashes every small category onto the
        # baseline, where templates/docs and js/css overlap within a pixel or
        # two. This one answers "what is actually growing?", which is the
        # question the page exists for, and spreads those same lines apart.
        "chart-relative-growth.svg": svg_chart(
            "Relative growth (first tracked month = 100)",
            labels,
            [
                (
                    name,
                    PALETTE[name],
                    [
                        round(v / loc(name)[0] * 100, 1) if loc(name)[0] else 100.0
                        for v in loc(name)
                    ],
                )
                for name in CATEGORIES
            ],
            "index",
            baseline=100,
        ),
    }

    out: list[str] = []
    add = out.append

    add("# Codebase development metrics")
    add("")
    add(
        "Generated by [`scripts/codebase_metrics.py`](../../scripts/codebase_metrics.py) — "
        "do not edit by hand. Refresh with `scripts/codebase_metrics.py`; a scheduled "
        "workflow also pushes a refresh branch on the first of each month."
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
    add("![feat: commits per month](chart-feature-commits.svg)")
    add("")
    add("## What is actually growing?")
    add("")
    add(
        "App code is surface area you have to hold in your head; tests are "
        "insurance. They grow for different reasons and only one of them is a "
        "warning sign."
    )
    add("")
    add("![App code vs. test code](chart-app-vs-tests.svg)")
    add("")
    add("### Lines by category")
    add("")
    add("![Lines by category](chart-lines-by-category.svg)")
    add("")
    add(
        "The same series indexed to their first tracked month, which separates "
        "the categories the chart above stacks onto the baseline. Anything flat "
        "along the dashed line is holding steady; docs below it are shrinking."
    )
    add("")
    add("![Relative growth](chart-relative-growth.svg)")
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

    files["README.md"] = "\n".join(out)
    files["metrics.json"] = json.dumps(data, indent=2, sort_keys=True) + "\n"
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if output is stale")
    parser.add_argument("--stdout", action="store_true", help="print README instead of writing")
    args = parser.parse_args()

    files = build(collect())

    if args.stdout:
        print(files["README.md"])
        return 0

    if args.check:
        stale = [
            name
            for name, want in files.items()
            if not (OUT_DIR / name).is_file() or (OUT_DIR / name).read_text("utf-8") != want
        ]
        if stale:
            print("Stale metrics output: " + ", ".join(sorted(stale)), file=sys.stderr)
            print("Run scripts/codebase_metrics.py to refresh.", file=sys.stderr)
            return 1
        print("Metrics output is current.")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (OUT_DIR / name).write_text(content, encoding="utf-8")
    print(f"Wrote {len(files)} files to {OUT_DIR.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
