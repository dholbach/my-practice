# Contributing

Thanks for your interest. This is a small solo project but PRs and issues are genuinely welcome — especially from practitioners who run similar setups.

## Before you start

Read the [status and limitations](README.md#status-and-limitations) section of the README. The code reflects one specific setup (Berlin, Germany, GLS Bank, single practitioner). Contributions that make it more adaptable without adding complexity for the existing use case are the sweet spot.

## Privacy — non-negotiable

This app handles personal health data. That sensitivity extends to contributions:

- **No real names** in issues, PRs, commit messages, code, or test fixtures. Use fictional names (`Max Mustermann`, `Anna Schmidt`) or client codes (`AB-1`, `XX-2`).
- **No real contact details** — use `mail@example.com`, `+49 123 456789`, etc.
- **No real invoices, session notes, or bank data** — invent plausible-looking fictional data instead.

If you're reporting a bug that involves real data from your own practice, anonymise it before posting.

## Setup

```bash
git clone https://github.com/dholbach/my-practice.git
cd my-practice
./dev.py start --build
./dev.py manage createsuperuser
./dev.py manage seed_sample_data   # loads fictional demo data
```

Full walkthrough: [docs/guides/GETTING_STARTED.md](docs/guides/GETTING_STARTED.md)

## Code conventions

- **Language**: code and comments in English; UI text (labels, buttons, messages) stays in German until i18n is done ([P-039](docs/projects/todo/P-039_I18N.md))
- **Style**: `./dev.py quality` runs ruff format + ruff lint + tests — must pass before a PR
- **Patterns**: check [docs/architecture/CODE_STRUCTURE.md](docs/architecture/CODE_STRUCTURE.md) before adding new views or utils; there are builder classes and helpers for most common tasks
- **Tests**: add a test for new behaviour; run the relevant test file during development, full suite before opening a PR

```bash
./dev.py test my_practice.tests.test_invoice   # targeted
./dev.py test                                   # full suite
./dev.py quality                                # format + lint + test
```

## Opening a PR

1. Fork the repo and create a branch from `main`
2. Make your changes, add tests if applicable
3. Run `./dev.py quality` — fix anything it flags
4. Open a PR using the template; fill in all sections
5. PRs are reviewed by the maintainer when time allows — this is a one-person project

## Issues vs. Projects

**GitHub issues** are the right place for anything a contributor could reasonably pick up: bugs, well-scoped feature requests, documentation gaps, or test coverage improvements. A good issue results in one PR (or a small handful).

**P-XXX planning projects** are used for larger efforts that need a design document before any PR makes sense — multi-session work, features with compliance or architecture implications, or things that are not yet ready for outside contribution. These live in [`docs/projects/`](docs/projects/) and are tracked in [`PROJECTS.md`](PROJECTS.md). If you open a feature request that turns out to be that scale, the maintainer will note it and link to the planning doc when one exists.

In short: **file an issue for anything you'd accept a PR for today**. If you're unsure, file the issue — it's easy to close or convert later.

## Issues

Use the issue templates. For bugs, include your Django/Docker versions and a minimal reproduction. For feature requests, explain the workflow problem you're solving, not just the solution you have in mind.

## License

By contributing, you agree that your contributions will be licensed under the project's [AGPL-3.0 license](LICENSE).
