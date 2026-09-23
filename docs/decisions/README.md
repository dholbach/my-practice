# Decision records

Short notes on choices that look wrong, redundant or arbitrary until you know
why they were made — the ones where the next person's instinct is to "clean it
up" and reintroduce the problem it was solving.

Most decisions do not need a record. Write one when **all three** hold:

1. The reasoning is not obvious from the code.
2. Someone could plausibly undo it while tidying.
3. Undoing it costs something real.

That is a deliberately high bar. A pattern everyone follows needs a line in
[CODEBASE_STANDARDS.md](../guides/CODEBASE_STANDARDS.md), not a record here.
Project *plans* live in [docs/projects/](../projects/); one-off analyses live
in [docs/notes/](../notes/). This directory is only for "why is it like this?".

## Format

`ADR-NNNN-short-slug.md`, numbered sequentially from the highest existing
number. Three headings — **Context**, **Decision**, **Consequences** — and keep
it to a screen. These are signposts; the authoritative detail stays next to the
code, and each record links to it.

Records are not edited to reflect later changes. If a decision is reversed, add
a new record and add a line at the top of the old one pointing at it.

## Index

| Record | Decision |
| --- | --- |
| [ADR-0001](ADR-0001-two-requirements-files.md) | `requirements-dev.txt` duplicates every runtime pin instead of using `-r` |
| [ADR-0002](ADR-0002-single-pre-commit-mechanism.md) | Exactly one git hook mechanism, ever |
| [ADR-0003](ADR-0003-repo-root-ruff-target-version.md) | Repo-root Python targets an older Python than the app |
| [ADR-0004](ADR-0004-prod-py-single-file.md) | `prod.py` ships as one stdlib-only file, duplicating a helper |
| [ADR-0005](ADR-0005-ci-docs-only-short-circuit.md) | Docs-only CI skipping happens inside each job |
| [ADR-0006](ADR-0006-minimum-supported-window-width.md) | The minimum supported window is 768px, and wide tables scroll |
