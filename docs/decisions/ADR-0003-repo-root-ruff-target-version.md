# ADR-0003 — Repo-root Python targets an older Python than the app

## Context

`app/pyproject.toml` sets `target-version = "py314"`: the app runs on Python
3.14 inside the container. Among other things, that lets ruff's formatter
normalise exception tuples to 3.14's bracketless `except A, B:` form, which the
app's code uses throughout.

`dev.py`, `prod.py` and `scripts/*.py` do not run in the container. They run on
whatever Python the contributor or self-hoster has. Formatting them under the
app's target would rewrite their `except` clauses into syntax that is a hard
`SyntaxError` on 3.13 and older — making `./dev.py` itself unrunnable for
anyone not already on 3.14, including the command they would use to fix it.

## Decision

A separate [`ruff.toml`](../../ruff.toml) at the repo root with
`target-version = "py310"`, mirroring the app's rule selection minus `DJ` (no
Django in those files). Ruff resolves config per file, so `app/**.py` picks up
`app/pyproject.toml` and root-level scripts pick up `ruff.toml`, whichever
directory the command is run from.

`known-first-party = ["my_practice"]` is declared explicitly there because
ruff's filesystem auto-detection gave different import grouping depending on
whether a file was resolved from the repo root or against the container's
`/app` mount.

## Consequences

- Two ruff configs. They are kept deliberately close; only `target-version`,
  the `DJ` rules and the isort setting differ.
- Raise the root `target-version` only when the oldest Python a contributor
  might run `./dev.py` with is new enough — which is not the same question as
  what the container runs.
