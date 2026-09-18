# ADR-0001 — `requirements-dev.txt` duplicates every runtime pin

## Context

`app/requirements-dev.txt` needs everything in `app/requirements.txt` plus the
tooling (ruff, mypy, pytest, …). The obvious spelling is `-r requirements.txt`
at the top.

Dependabot does not resolve `-r` includes when it generates a security-update
PR. With the include in place, every runtime CVE alert was raised against the
dev file and had no fix path — Dependabot could see the vulnerable package but
could not find a line to bump.

## Decision

Duplicate every runtime pin in both files, and enforce the duplication with
[`scripts/check_requirements_sync.py`](../../scripts/check_requirements_sync.py).

The check is one-directional: every pin in `requirements.txt` must appear in
`requirements-dev.txt` at the same version, while extra entries in the dev file
are expected. It runs in the pre-commit hooks, in `./dev.py quality`, and in CI.

## Consequences

- Two files to update for one dependency bump. The checker makes forgetting a
  failed build rather than a silent divergence.
- The divergence is not hypothetical: before the checker existed, the
  `sqlparse` pin closing PYSEC-2026-3696..3699 was in `requirements.txt` only.
  CI installs `requirements-dev.txt`, so the whole suite ran against the
  vulnerable version the production image did not ship.
- If Dependabot ever learns to resolve `-r` includes, this can be revisited —
  and then both this record and the checker go.
