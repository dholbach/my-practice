# Documentation

---

## User Guides

How to use and operate the system:

- [FEATURES.md](FEATURES.md) — Complete feature overview
- [guides/GETTING_STARTED.md](guides/GETTING_STARTED.md) — First-time setup
- [guides/CUSTOMISATION.md](guides/CUSTOMISATION.md) — What to replace before using for your own practice
- [guides/EMAIL_IMPLEMENTATION.md](guides/EMAIL_IMPLEMENTATION.md) — Email sending via Proton Bridge
- [guides/CLIENT_TAGGING.md](guides/CLIENT_TAGGING.md) — Tag system and workflow
- [guides/BACKUP_SETUP.md](guides/BACKUP_SETUP.md) — Backup strategy and automation
- [guides/CLINICAL_DATA_SECURITY.md](guides/CLINICAL_DATA_SECURITY.md) — Encryption model, GDPR obligations, open questions
- [guides/EMERGENCY_ACCESS_PLANNING.md](guides/EMERGENCY_ACCESS_PLANNING.md) — Business continuity for solo practitioners

---

## Architecture

How the codebase is structured — useful for contributors and for onboarding:

- [architecture/CODE_STRUCTURE.md](architecture/CODE_STRUCTURE.md) — Models, views, utils, patterns
- [architecture/PERFORMANCE.md](architecture/PERFORMANCE.md) — Query optimisation, indexes, N+1 fixes

---

## Operations

Running this specific installation:

- [operations/SCRIPTS.md](operations/SCRIPTS.md) — `dev.py` CLI reference, backup/restore, systemd timers
- [operations/SECURITY.md](operations/SECURITY.md) — Production security checklist, env vars
- [operations/DATA_REGISTER.md](operations/DATA_REGISTER.md) — External data flows and GDPR processor register
- [operations/DPIA-template.md](operations/DPIA-template.md) — Data Protection Impact Assessment template

---

## Project Management

P-XXX projects are used for larger efforts that need a design document before a PR makes sense: multi-session work, features with compliance implications, or things not yet ready for outside contribution. Well-scoped bugs and features go in [GitHub Issues](https://github.com/dholbach/my-practice/issues) instead. See [CONTRIBUTING.md](../CONTRIBUTING.md#issues-vs-projects) for the full distinction.

- [../PROJECTS.md](../PROJECTS.md) — Numbered projects (TODO → WIP → DONE)
- [GitHub Issues](https://github.com/dholbach/my-practice/issues) — Bug reports, enhancements, operational tasks
- [projects/todo/](projects/todo/) — Detailed project docs (upcoming)
- [projects/wip/](projects/wip/) — In-progress project docs
- [projects/done/](projects/done/) — Completed project docs

---

## Notes

Analyses, workarounds, and observations that don't fit anywhere else:

- [notes/TYPE_CHECKING_NOTES.md](notes/TYPE_CHECKING_NOTES.md) — Mypy false positives and known quirks

---

## History

- [CHANGELOG.md](CHANGELOG.md) — Feature history and releases
