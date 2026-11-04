# Project Instructions

Therapy practice payment/invoicing system built with Django, PostgreSQL, running in Docker.

**Detailed contracts live in [docs/guides/CODEBASE_STANDARDS.md](docs/guides/CODEBASE_STANDARDS.md)** —
worked examples, the failure behind each rule, every guardrail test and what it can't see.
This file is the summary; read the relevant standards section before touching that area.

## 🔒 Privacy & Data Protection (CRITICAL)

**Never violate these** — in docs, code, examples, commit messages, comments, test fixtures and migration defaults:
1. **No real names**: dummy names only ("Max Mustermann", "Anna Schmidt", "Maria Musterfrau").
2. **No real contact info**: "mail@example.com", "contact@practice.example", "+49 123 456789".
3. **Fictional examples**: client codes XX-1, YY-2, AB-3; invoices INV-001; bank names "M. Schmidt", "Test GmbH".
4. **Review for leaked PII before every commit.**

**Privacy mode (M-PAT-08)** — `html.privacy-mode` is a client-side toggle, on by default, so a missing blur
looks normal whenever it's off. Use `<span class="sensitive-data">` for a name beside its client code,
`|privacy_name` where there's no code to fall back on (inquiries, pickers whose rows must be told apart),
and nothing for codes, invoice numbers, form inputs or `<option>` text (selects show the code only).
`test_privacy_coverage.py` ratchets both under- and over-blur; shrink `KNOWN_UNPROTECTED`, never grow it.

## i18n (P-039) — every user-facing string is wrapped

- **English msgids** everywhere: `{% trans "Switch" %}`, `_("…")`. German lives only in `locale/de/LC_MESSAGES/django.po`. Never write literal German or literal English UI text.
- New files ship fully wrapped; when editing a file, wrap any string you touch. Templates `{% load i18n %}`.
- **`gettext_lazy`** for anything evaluated at import/class-definition time (`verbose_name`, `help_text`, form `label=`, `fieldsets`, admin descriptions, `success_message`); **eager `gettext as _`** only per-request (view bodies, `messages.*()`, `JsonResponse`, form errors). Backwards = locale frozen at startup, invisible in review.
- Strings needed in JS go through the template via `data-*` attributes, never as `.js` literals.
- Reuse existing msgids (grep `django.po`) before minting new ones.
- After changing strings: `./dev.py i18n`, then check the `django.po` diff for `#, fuzzy` entries and empty `msgstr ""` — both need a real German translation before committing.
- Exemptions (PDF templates, bilingual email content builders, clinical scaffolding templates, free-text data like `ClientTag`), the per-document `_de`/`_en` language mechanism, and the guardrail's blind spots: [CODEBASE_STANDARDS.md § Internationalisation](docs/guides/CODEBASE_STANDARDS.md#internationalisation-p-039). `KNOWN_UNWRAPPED_TEMPLATES` in `test_i18n_coverage.py` stays empty.

## Development

Use `./dev.py` for everything:
```bash
./dev.py start | restart --force | logs -f   # containers (--force reloads .env)
./dev.py test [my_practice.tests.test_x]     # Django + JS tests, optionally one module
./dev.py test --smart                        # only tests affected by changes (testmon)
./dev.py test --fast                         # full suite, parallel + failfast
./dev.py shell | manage <cmd> | run <script.py>
./dev.py lint                                # ruff format + lint
./dev.py quality                             # lint + Tailwind build + full suite
./dev.py i18n                                # extract + compile translations
./dev.py install-hooks                       # pre-commit hooks, once per clone
./dev.py smoke [vX.Y.Z]                      # boot a released image against a throwaway DB
```

**Testing scope**: run the test file(s) for what you touched while developing; widen to cover shared models/utils before committing (`--smart` when unsure); full suite once at the end of a session or before a release.

**Git**: `main` is branch-protected — every change, even docs, goes through a feature branch and `gh pr create`. `.pre-commit-config.yaml` is the only hook mechanism — never add `core.hooksPath`. CI additionally runs gitleaks over full history, `check --deploy`, mypy on the strict modules and the requirements-sync check ([§ Repository Tooling](docs/guides/CODEBASE_STANDARDS.md#repository-tooling--guardrails)).

**Releases**: [docs/operations/RELEASE.md](docs/operations/RELEASE.md). The three version strings (`version.py`, `prod.py`, `docker-compose.prod.yml`) must match, and the GitHub release needs real highlights — `./prod.py update` reads them.

## Architecture & patterns

Models, views and utils are domain-split modules under `app/my_practice/{models,views,utils}/`; templates under `app/templates/` with reusable pieces in `includes/`. **Check `utils/` before writing new logic** — module map in [docs/architecture/CODE_STRUCTURE.md](docs/architecture/CODE_STRUCTURE.md), canonical-pattern tables in CODEBASE_STANDARDS.md.

| Need | Use |
| --- | --- |
| Revenue / date-filtered invoice figures | `RevenueCalculator` (never hand-built `invoice_date__year`/`status` filters) |
| Invoice search/filter | `InvoiceFilterHelper(qs).apply_filters(...)` |
| Complex view context | `FinancialListContextBuilder`, `AnalyticsDashboardBuilder`, other builders in `utils/` |
| Session counts | `count_sessions(items)` |
| Dates / working days | `DateRangeHelper`; `count_working_days` with `berlin_public_holidays` |
| CRUD views | `PracticeScoped{List,Create,Update,Delete}View`, `NextRedirectMixin`, `InvoiceFormsetMixin` (`views/crud_mixins.py`) |
| Forms | `StyledFormMixin` (no manual widget classes), `DateFormField` |
| New models | `TimestampedModel` base |

**Practice scoping fails closed.** Query helpers take `practice` as a required keyword and filter with `scope_to_practice(qs, practice[, "client__practice"])`: `None` gives nothing, `ALL_PRACTICES` gives everything. Never `if practice: qs = qs.filter(...)`. Some models are deliberately shared — see CODEBASE_STANDARDS.md § Queries. `test_practice_scoping.py` guards it; shrink `KNOWN_UNBOUND_QUERIES`, never grow it.

### Numbered patterns (M-PAT-01 … M-PAT-09)

Each exists because the bug it prevents is invisible in review. Worked examples: [CODEBASE_STANDARDS.md § Patterns Reference](docs/guides/CODEBASE_STANDARDS.md#patterns-reference-m-pat-01--m-pat-09).

| | Rule |
| --- | --- |
| **M-PAT-01** Error handling | Form views: `messages.error()` + `form_invalid()`. API views: `JsonResponse` with a status code. Management commands: log, then raise `CommandError`. |
| **M-PAT-02** Date filters | Always go through `RevenueCalculator`. |
| **M-PAT-03** Charts | Chart.js through `MPChart` (`static/js/charts.js`), in a fixed-height `.chart-wrapper--*`. |
| **M-PAT-04** CSS | Everything in `app/static/css/tailwind.css` (`@layer components`). No `<style>` blocks, no new `.css` files, no page CSS block. PDF templates exempt. |
| **M-PAT-05** Working days | `DateRangeHelper.count_working_days` with Berlin holidays (set built once per call); never `round(days * 5/7)`. |
| **M-PAT-06** Form draft guard | Long-text forms opt in with `data-draft-guard` plus the three `data-draft-*` labels, reusing those msgids verbatim. |
| **M-PAT-07** CSS tokens | Real `--color-*` tokens only (grep the `@theme` block); never invent a name, never hardcode hex on a semantic class. `text-link` for brand-coloured text, not `text-primary`. |
| **M-PAT-08** Privacy mode | `.sensitive-data` beside a code, `\|privacy_name` without one, nothing for codes / inputs / `<option>`. |
| **M-PAT-09** Narrow windows | Minimum viewport 768px. Flex button groups `flex-wrap: wrap`; every `<table>` directly in `.table-container`; 6+ columns add `table-container--wide`. |

**Frontend gotchas the test client can't see**:
- **CSP**: inline `<script>` needs `nonce="{{ csp_nonce }}"`; no `onclick=`-style attributes (use `addEventListener` / Alpine `x-on:`). Alpine is the CSP build — no globals (`window`, `confirm`, `setTimeout`…), no arrow functions. Use the `data-confirm`/`data-print`/`data-navigate`/`data-submit-on-change`/`data-copy`/`data-post-link` helpers in `static/js/ui_actions.js`, or an `Alpine.data()` component.
- **Money** in templates: `|currency` / `|currency_rounded`, never `floatformat` + `€`.
- Every guardrail test above is a ratchet: shrink its allowlist, never grow it to make new code pass.

## Code style

- **English** for all identifiers, comments, docstrings, filenames, URL slugs and docs (P-038). When touching a file with German comments/identifiers, translate them in the same commit.
- Relative imports for app code (`from ..models import Client`).
- Python 3.13 type hints: `str | None`, `list[str]`, `dict[str, int]`.
- `select_related` for FK access, `prefetch_related` for reverse relations, `.only()` when building maps.
- Docstrings on public functions/classes; comments explain *why*. No dead or commented-out code.
- Formatting: ruff (`./dev.py lint`).
- New feature placement: model → `models/<domain>.py`, view → `views/<feature>_views.py`, util → `utils/<purpose>.py` (update each package's `__init__.py`), tests → `tests/test_<module>.py` (Django `TestCase`).

## Documentation

Where each kind of doc belongs: [CODEBASE_STANDARDS.md § Documentation](docs/guides/CODEBASE_STANDARDS.md#documentation). Decisions that would otherwise survive only as a code comment become an ADR in [docs/decisions/](docs/decisions/). Projects are tracked in [PROJECTS.md](PROJECTS.md) as P-XXX — a new one takes the lowest unused number.

**Gardening pass at the end of each session**, before committing:
- PROJECTS.md: add a "Recent Activity" entry and keep at most two; remove finished items from the Backlog.
- docs/FEATURES.md: one line per user-facing addition.
- Completed project: mark it done in PROJECTS.md, then delete its doc (or move it to `done/` only if code or another doc links to it for its reasoning).

Periodic review: `./dev.py review` monthly, `--full` quarterly; it prints its own checklist.
