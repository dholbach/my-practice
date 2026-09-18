# ADR-0002 — Exactly one git hook mechanism, ever

## Context

The repo had two hook mechanisms at once:

- `.pre-commit-config.yaml`, installed by `pre-commit install` into
  `.git/hooks/` — ruff, gitleaks, the `.env` drift check, file checks.
- `.githooks/pre-commit`, installed by `./dev.py install-hooks` pointing
  `core.hooksPath` at it — ruff plus the PII guard.

`core.hooksPath` overrides `.git/hooks/` wholesale. Whichever was installed
last turned the other off, with no output saying so. In practice neither was
installed in a fresh clone: 13 files carried trailing whitespace the hooks
would have fixed, and the gitleaks secret scan had never run at all on a
repository that handles health data.

## Decision

`.pre-commit-config.yaml` is the only mechanism. `.githooks/` is deleted and
its PII guard is a local hook in that config. `./dev.py install-hooks` clears
any stale `core.hooksPath` before installing, because `pre-commit install`
refuses while it is set.

CI runs `pre-commit run --all-files`, so a clone that never installed the hooks
is still covered.

## Consequences

- Never add a second mechanism. A hook that must run belongs in
  `.pre-commit-config.yaml`.
- Hooks are only as good as each clone running `./dev.py install-hooks`; CI is
  the backstop, which moves the feedback from `git commit` to the PR.
- `SKIP=gitleaks` in CI is deliberate and not an oversight: the hook is
  `gitleaks protect --staged`, which scans the index, and under `--all-files`
  nothing is staged — so it reports a pass without looking at anything. A
  separate CI step runs `gitleaks detect` over full history instead. Full
  contract in [CODEBASE_STANDARDS.md](../guides/CODEBASE_STANDARDS.md).
