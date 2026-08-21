# Post-release review — after v0.5.0 / v0.5.1 / v0.5.2

Findings from a review session on 2026-08-21, covering the 98 commits between
v0.4.3 and v0.5.2. Two items were fixed in the same session; the rest are
recorded here as a worklist.

## Context: what those three releases were

Almost entirely internal quality, not features. Guardrails built
(`test_i18n_coverage` incl. the extraction-drift check, `test_css_tokens`), test
backfill (135 builder tests, 23 for `form_draft_guard.js`, admin classes,
management commands), UI regression fixes found by eyeballing rendered pages
(5 dark-mode contrast failures, button contrast, flex stretching, a no-opping
`appendDocRow()`), and two rounds of Docker image slimming. Only two user-facing
changes: free-form invoice items and the practice-setup redirect.

The fix-commit distribution says the same thing — `tailwind.css` (5 fix
commits), the invoice PDF templates (3 each), `client_detail.html` (3),
`crud_mixins.py` (3). Repeat fixes concentrated in the presentation layer,
mostly found by looking at a page rather than by a test.

## Done in this session

- **CI now runs the test suite** (closes #8). The workflow was lint-only, so
  every guardrail listed above ran only when someone remembered
  `./dev.py quality`. Also fixed a drifted second copy of the ruff pin (CI ran
  0.15.18 against requirements-dev.txt's 0.16.3).
- **`update_check` caches failures.** The GitHub releases lookup runs in a
  context processor and a failed lookup was never cached, so an unreachable
  GitHub meant every authenticated page render paid the full 3s timeout again,
  indefinitely. Now cached as an empty string for 15 minutes; the bare
  `except Exception` narrowed to `(OSError, ValueError)` and logged.
- **Two encrypted-field tests fixed.** CI's first two runs caught
  `test_gebueh.py` and `test_sync_focus_queue_tasks.py` writing non-empty values
  to Art. 9 fields without `@override_settings(FERNET_KEY=...)`. Neither had ever
  passed on a clean checkout — they were green only because a developer `.env`
  exported a real key into the test process.
- **CI re-runs the test suite serially on failure.** Django's parallel runner
  pickles results back to the parent, and an errored test whose traceback can't
  be pickled kills the run at the first error, hiding everything after it. That
  is exactly how the two encrypted-field bugs above took two red rounds instead
  of one. Free on a green build.
- **Repo-root Python is linted by CI, with its own `ruff.toml`** (items 4 and 5
  below). See "Resolved: which ruff config is authoritative" for what that
  turned up.

## Remaining — recommended order

### 1. JavaScript is the last untested surface

Of seven hand-written JS files, only `form_draft_guard.js` and the chart modules
have tests. Untested: `bank_review.js`, `global-search.js`, `keyboard-nav.js`,
`widgets.js`, `expense_form.js`.

Not theoretical: `bank_review.js` is where the hardcoded-German-literals i18n
bug lived, and `appendDocRow()` silently no-opped for an entire release after
the P-094 tab redesign moved the list it targeted. Both would have been caught
by a node test of the kind `form_draft_guard.test.js` already demonstrates —
plain `node <file>`, no framework, no node_modules.

Now that CI runs the node suites, each new test file added there is enforced on
every PR.

### 2. Perf regression ratchet is thin

`assertNumQueries` appears in exactly two test files (`test_views_analytics`,
`test_views_dashboard`). #276 fixed an analytics page firing 4,088 queries in
2.3s; nothing currently stops a future missing `select_related` from putting it
back. Worth extending to client detail and the Focus Queue, the other two pages
with heavy related-object access.

### 3. `utils/file_processing.py` exception audit

Seven broad `except Exception` handlers, including one bare
`except Exception: pass` at lines 186-189. This is the module that hands
uploads to Pillow and shells out to Ghostscript — the untrusted-input path.
#355 narrowed three such blocks elsewhere for exactly this reason; this file
was the one where it matters most and it was skipped.

### 4. Widen the ruff rule selection — DONE

`B`, `DJ`, `C4` and `SIM` are now selected; all 24 findings fixed except one
documented `DJ012` ignore. The original measurement, for reference:

| Rules | Findings |
| --- | --- |
| `B` (bugbear) | 4 |
| `DJ` (Django) | 2 |
| `C4` (comprehensions) | 6 |
| `SIM` | 14 |

26 findings total — a near-zero-noise ratchet expansion, and CI enforces it now.

`S` (bandit) reports 302, but 268 are `S106` hardcoded test passwords; a
`per-file-ignores` for `tests/` makes the rest reviewable. For the record, all
10 `mark_safe` call sites it flags were audited this session and are correctly
escaped or static — #297's lesson did stick.

**`I` (isort) — DONE**, in its own PR as planned. 81 files reordered, no import
added or removed (verified by comparing the set of imported names per file
before and after) and all three package `__all__` exports byte-identical.

The one thing worth knowing if this ever needs redoing: reordering a package
`__init__.py` can expose a latent import cycle that the previous order happened
to avoid. `utils/calendar_import_helpers.py` imports its own package
(`from ..utils import get_next_invoice_number, sync_no_next_session_tag`), and
both names come from modules that sort *after* it — so if `__init__.py` imported
it, alphabetising would have broken app startup outright. It doesn't: that module
is only ever imported lazily by its callers. Nothing else in `models/`, `utils/`,
`views/` or `admin/` imports its own package, the deferred post-`django.setup()`
imports in `check_bank_duplicates.py` and `create_default_tags.py` stayed put
(ruff won't hoist imports across statements), and signals are wired in
`apps.py ready()` rather than at module import.

### 5. Repo-root Python is unchecked by CI — DONE

Resolved; kept below because the answer matters.

**Which ruff config is authoritative.** Neither, as it turned out — the root
files need their *own*. `app/pyproject.toml` sets `target-version = "py314"`,
under which the formatter rewrites `except (A, B):` into 3.14's bracketless
`except A, B:`. The app runs on 3.14 in the container, so that is correct there.
But `dev.py`, `prod.py` and `scripts/*.py` run on the **host** Python, where that
form is a hard `SyntaxError` on 3.13 and older. Running `./dev.py lint --write`
today would therefore have rewritten `dev.py` into a file that its own users
could not execute.

They now have a repo-root `ruff.toml` pinned to `target-version = "py310"` (all
five files verified to compile under 3.10), and CI lints and format-checks them
natively. `dev.py`'s stdin path — which pipes each file through the *container's*
ruff, where the root `ruff.toml` isn't mounted — passes the target-version
through as an inline `--config`, read out of `ruff.toml` rather than duplicated.

The `PERF401` in `scripts/check_pii.py` is fixed, along with three more findings
the widened rules surfaced there, and the files are now format-clean at the
project's 100-column width (they had been sitting at ruff's default 88).

<details>
<summary>Original note</summary>

`dev.py`, `prod.py` and `scripts/*.py` are linted by `./dev.py quality` (via the
container's ruff over stdin, since the container only mounts `app/`) but not by
CI. Two things to verify locally:

- `scripts/check_pii.py:89` has a real `PERF401` finding under the project's own
  ruff config.
- Under ruff 0.16.3 with `app/pyproject.toml`, `dev.py` and `prod.py` are not
  format-clean — ruff wants to rewrap them to 100 cols and convert
  `except (A, B):` to the py314 bracketless form. On disk they are at ruff's
  default 88 cols with parenthesized tuples, which suggests the stdin path is
  resolving different config than a direct run, or they haven't been reformatted
  since the 0.15.18 → 0.16.3 bump.

Resolve which is authoritative before adding these files to CI, otherwise the
lint job goes red on the first PR.

</details>

### 6. No explicit `CACHES` configuration

`config/settings.py` has no `CACHES` block, so everything falls back to
per-process `LocMemCache`. The `update_check` fix above is correct under it, but
each gunicorn worker warms its own copy and every restart is cold. Choosing a
real backend is a deployment decision (a DB-table cache needs no new service),
so it is recorded here rather than assumed.

### 7. Loose scripts at `app/` root

`check_bank_duplicates.py`, `cleanup_test_db.py`, `create_initial_data.py` and
`report_monthly_sessions.py` are referenced by nothing outside CHANGELOG
history. They are `./dev.py run`-style operator scripts, but they sit outside
`scripts/`, ship inside the image, and `create_initial_data.py` overlaps with
`seed_sample_data`. The #323/#325 dead-code sweep missed them because vulture
finds unused *names*, not unreferenced *modules*.

### 8. Duplicated tool configuration

vulture is configured twice with different `paths` — `app/pyproject.toml`
`[tool.vulture]` and `setup.cfg` `[vulture]`. `setup.cfg` also still carries a
`[pycodestyle]` section that nothing has read since the ruff migration.

## Quick wins in the open issue list

Ranked by effort-to-value out of the 21 open issues:

| Issue | Why it's quick |
| --- | --- |
| ~~#8~~ | Done this session. |
| #192 — Google Calendar name hardcoded "Praxis" | Exactly 3 call sites: `calendar_views.py:94`, `:189`, `fetch_calendar_events.py:105`. One `Practice` field or env var. |
| #193 — `TIME_ZONE`/`LANGUAGE_CODE` via env | Two lines in `config/settings.py` → `os.environ.get`. |
| #12 — Generalise `berlin_public_holidays()` | Already isolated behind one function in `utils/practice_days.py`; add a state parameter. |
| #148 — Update screenshots and user docs | Genuinely stale after the v0.5.1 client-detail redesign. |
| #98 — `seed --language` flag | Contained to one management command. |

Not quick, despite looking it: #343 (throttling + 2FA), #11 / #194 (bank CSV
configurability — already three comments of scope creep), #77 (command palette),
#290–#294 (five separate analytics features), #114 (backup restore smoketest).
