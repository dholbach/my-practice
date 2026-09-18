# ADR-0004 — `prod.py` ships as one stdlib-only file, duplicating a helper

## Context

`prod.py` is what a self-hoster downloads: `curl -O prod.py` into an otherwise
empty directory, where `setup` then fetches the compose file. It therefore
cannot import a shared module — there is nothing else on disk yet — and cannot
depend on anything outside the standard library.

It overlaps slightly with `dev.py`. The only sharing direction that would work
(`dev.py` importing `prod.py`) means moving workstation concerns into the file
that has to stay minimal.

## Decision

Keep the copies. Of 67 top-level functions across the two scripts, exactly one
is genuinely duplicated, and
[`scripts/check_shared_helpers.py`](../../scripts/check_shared_helpers.py)
fails the build if the copies diverge.

The checker is not a general "these files look alike" check. Every other
similarity between the two is either a deliberate difference or two different
programs that happen to spell a command the same way.

## Consequences

- One function must be edited in two places. The checker makes that a failed
  build rather than a silent divergence.
- Adding to `DUPLICATED` in the checker is a real decision: only do it when a
  difference between the copies would be a bug rather than a choice.
- `prod.py` stays stdlib-only. A dependency there is a dependency the
  self-hoster has to install before they can install anything.
