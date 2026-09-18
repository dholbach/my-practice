# ADR-0005 — Docs-only CI skipping happens inside each job

## Context

A docs-only PR does not need two minutes of tests. The obvious ways to skip are
`paths-ignore:` on the workflow, or `if:` on the job.

Both break merging. `lint` and `test` are required status checks on `main`'s
ruleset with no bypass actors, and a required check that never runs stays
pending forever — which would make every docs PR permanently unmergeable.

A third option, a `changes` job feeding the others through `needs:`, avoids
that but turns any failure in the upstream job into *skipped* dependent jobs
rather than red ones, which is a far less obvious state to debug on a blocked
PR.

## Decision

Both jobs always run. Each starts with
[`scripts/ci_docs_only.sh`](../../scripts/ci_docs_only.sh), which writes
`code=true|false` to `$GITHUB_OUTPUT`, and every expensive step is gated on it.
A docs-only PR satisfies both required checks with a real success in seconds.

The script is shared rather than inlined because it was previously two inline
copies that had to be edited in lockstep.

Pushes to `main` never skip: `main` must stay fully verified regardless of what
a PR was allowed to skip.

## Consequences

- Every new expensive step needs its own `if: steps.scope.outputs.code ==
  'true'`. Forgetting it costs time on docs PRs but never correctness.
- A new job needs its own copy of the detect step — three lines calling the
  shared script, not a copy of the logic.
- Do not "simplify" this into `paths-ignore:`, an `if:` on the job, or a
  `needs:` chain without first checking what `main`'s ruleset requires.
