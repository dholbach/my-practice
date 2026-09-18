# Codebase Standards & Scan Reference

This document defines what "good" looks like in each layer of the codebase
and provides the anti-patterns checklist used during periodic reviews
(`./dev.py review`). When in doubt, the canonical example beats the description.

---

## Queries & Data Access

### Canonical patterns

| Need | Use |
|------|-----|
| Revenue totals or breakdowns | `RevenueCalculator.get_total_revenue()` / `get_status_breakdown()` |
| Client revenue subquery | `RevenueCalculator.get_client_revenue_subquery()` |
| Invoice filtering (search, year, status, amount) | `InvoiceFilterHelper(qs).apply_filters(...)` |
| Practice-scoped queryset | inherit `PracticeScopedListView` or call `.for_current_practice(request)` |
| Date ranges | `DateRangeHelper(start, end)` |
| Working days with holidays | `DateRangeHelper.count_working_days(start, end, holidays)` — never `round(days*5/7)` |
| Session counting | `count_sessions(items)` — never inline `(duration/60)*quantity` |

### Anti-patterns to flag

- `Invoice.objects.filter(invoice_date__year=year, status='paid')` inline in a view → use `RevenueCalculator`
- `for client in clients: client.invoices.all()` → N+1; use `prefetch_related`
- `.filter(practice=request.current_practice)` duplicated across views → use `for_current_practice()`
- `Client.objects.all()` without `.select_related()` when FK fields are accessed → add `.select_related()`
- Manual session sum loops → `count_sessions()` / `count_session_hours()`
- `round(days * 5/7)` for working day approximation → `DateRangeHelper.count_working_days`

---

## Views & Business Logic

### Canonical patterns

| Need | Use |
|------|-----|
| List view (practice-scoped) | `PracticeScopedListView` |
| Create/update/delete | `PracticeScopedCreateView`, `PracticeScopedUpdateView`, `PracticeScopedDeleteView` |
| Invoice formsets | `InvoiceFormsetMixin` |
| Complex context (financial lists) | `FinancialListContextBuilder(qs).build_context(...)` |
| Complex context (analytics) | `AnalyticsDashboardBuilder(start, end).build_context()` |
| Dashboard widgets | per-widget builder class in `utils/dashboard_widgets.py` |
| Post-edit navigation | `get_success_url()` checking `request.POST/GET.get("next")` first |
| Form errors in views | `messages.error()` + `form_invalid()` — not bare `raise` |
| API responses | `JsonResponse({"success": True, "data": ...})` / `status=400` on errors |

### Anti-patterns to flag

- Function-based views doing complex filtering/aggregation inline → extract a helper/builder
- `success_url = reverse_lazy("some_list")` without `get_success_url()` / `next=` support
- View directly importing and calling ORM methods that belong in `RevenueCalculator` or a QuerySet method
- `from my_practice.models import X` in views (absolute import) → use relative `from ..models import X`
- Missing `select_related` / `prefetch_related` on querysets that loop over FK fields
- Permission check duplicated across multiple views → factor into mixin or `get_object()`

---

## Models

### Canonical patterns

- New models needing timestamps: inherit `TimestampedModel` (`created_at`, `updated_at`)
- Complex queryset logic: add methods to a custom `QuerySet` class, not to views
- `Meta.ordering` set to the most common sort order (avoids scattered `.order_by()` calls)
- `__str__` returns a human-readable identifier (client code + type, not just pk)
- Type hints use Python 3.12+ syntax: `str | None`, `list[str]`, `dict[str, int]`

### Anti-patterns to flag

- Model without `TimestampedModel` base when `created_at`/`updated_at` would be useful
- Business logic in `save()` overrides that belongs in a service/signal
- ForeignKey without `on_delete` specified
- `Optional[X]` / `List[X]` / `Dict[K, V]` type hints → use `X | None` / `list[X]` / `dict[K, V]`
- Inline query in a model method that duplicates logic already in a manager/QuerySet

---

## Templates & CSS

### Canonical patterns

- CSS lives in `static/css/<page-name>.css`, loaded via `{% block extra_css %}`
- No bare `<style>` blocks in templates (except PDF templates — they require inline)
- Form widgets styled via `StyledFormMixin` — no manual `attrs={"class": "form-control"}`
- Date inputs use `DateFormField` — not manual `type="date"` attrs
- Reusable snippets live in `templates/includes/`
- Delete views use `PracticeScopedDeleteView` — no wrapper functions

### Dark-mode contract (M-PAT-07)

**Use the real token names.** They are all prefixed `--color-`: `--color-bg-primary`,
`--color-bg-secondary`, `--color-surface`, `--color-text-primary`,
`--color-text-secondary`, `--color-border`, `--color-link`, `--color-primary`, and the
semantic pairs `--color-success`/`--color-success-bg`, `--color-warning`/`--color-warning-bg`,
`--color-danger`/`--color-danger-bg`. Grep the `@theme` block at the bottom of
`tailwind.css` for the full list before inventing one.

This matters more than it looks. `var(--made-up-name)` with no fallback makes the whole
declaration invalid at computed-value time, so the property is *dropped* and silently
falls back to inherited/initial — the background or hover highlight simply never renders.
With a hardcoded fallback (`var(--made-up-name, #333)`) the fallback wins permanently,
which defeats the token and breaks dark mode. Both had live instances in the stylesheet
until they were found by measuring contrast in a real browser.

Every CSS rule that sets `background` to a themed variable must also set an explicit
`color`. Omitting `color` causes dark-on-dark text when the background goes dark but the
inherited text colour doesn't follow.

```css
/* Good */
.my-card {
    background: var(--color-surface);
    color: var(--color-text-primary);
}

/* Bad — text colour is unspecified; breaks in dark mode */
.my-card {
    background: var(--color-surface);
}
```

Equally bad, and harder to spot: a hardcoded background with a tokenised text colour. The
background stays light in dark mode while the text goes near-white, giving a contrast
ratio around 1.0 — invisible, not merely low.

```css
/* Bad — #f0fff4 doesn't flip with the theme, but the inherited colour does */
.my-step.step-done { background: #f0fff4; }

/* Good */
.my-step.step-done { background: var(--color-success-bg); color: var(--color-success); }
```

Links inside themed containers must scope a link-colour rule so they use the theme token
rather than the browser default (`#0000ee`, invisible on dark backgrounds):

```css
.my-container {
    background: var(--color-bg-secondary);
    color: var(--color-text-primary);

    a { color: var(--color-link); }
}
```

`my_practice/tests/test_css_tokens.py` enforces the first two rules as a ratchet: it fails
on a `var(--x)` whose token is never defined, and on new hardcoded hex on a semantic
component class. Its allowlist covers what is deliberately theme-independent (brand
gradients, fixed swatch palettes, coloured buttons) — shrink it, don't grow it.

Note: a global `a { color: var(--color-link); }` rule in `@layer base` in `tailwind.css` handles the base case. You only need the scoped rule when the container overrides `color` to something that would make the global rule look wrong (e.g. white text on a coloured background where links should also be white).

### Privacy-mode contract (M-PAT-08)

Privacy mode is a shoulder-surfing toggle: `body.privacy-mode` (localStorage, client-side
only — the server never knows it is on) blurs everything inside a `.sensitive-data`
element. Two mistakes are possible, and neither is visible in review or in normal use,
because nothing renders differently unless the toggle happens to be on:

- **under-blur** — a personal field rendered outside any `.sensitive-data` element;
- **over-blur** — `.sensitive-data` around something that was never personal, which hides a
  form label or a client code that *is* the privacy-safe representation.

Both have been fixed one site at a time more than once (#321, #424, #426).
`my_practice/tests/test_privacy_coverage.py` now ratchets both directions.

Which treatment to use:

| Situation | Treatment |
|---|---|
| Name shown beside its client code, or anywhere the record is already identified | `<span class="sensitive-data">` — full blur |
| Name with no code to fall back on (inquiries; any picker where rows must be told apart) | `\|privacy_name` — first letter of each word stays legible, rest blurred |
| Client code, invoice number, date, status | nothing — these are already the privacy-safe form |
| Form inputs, labels, `<option>` text | nothing — never blurred anywhere; `<option>` text is painted by the OS widget and a CSS blur cannot reach it, so a select shows the code only (`Client.__str__`) |
| PDF templates | nothing — a document needs the real name to be valid |

A value needed by JavaScript is a separate question from a blur: the guardrail reports
`<script>` hits with a `script:` prefix, and the answer is "check what the JS does with
it" — a name passed to `fetch()` never reaches the page, one written into `innerHTML`
leaks exactly like body text (which is how the command palette shipped unblurred results
in #424).

### Anti-patterns to flag

- `<style>` block inside a template `{% block extra_css %}` → move to `@layer components` in `tailwind.css`
- New `.css` file created for a page → move into `tailwind.css @layer components` instead
- `attrs={"class": "form-control"}` on form fields → use `StyledFormMixin`
- Inline `style="..."` on elements that should use CSS classes → replace with class
- Hardcoded colours (`#2d3748`, `#a5b4fc`) in templates or CSS → use `var(--color-*)` tokens
- `background: var(--*)` without a matching `color:` rule → dark-on-dark regression risk (M-PAT-07)
- `var(--some-token)` where the token isn't defined in `tailwind.css` → declaration silently dropped (M-PAT-07)
- `.text-success` / `.text-warning` / `.text-danger` / `.text-info` are now tokenised — don't add hardcoded hex equivalents
- `{{ client.full_name }}` without `sensitive-data` class, or `sensitive-data` on something that isn't personal (a client code, a form label) — both directions are caught by `test_privacy_coverage.py` (M-PAT-08)
- New template file with a German filename → rename to English (P-038)

---

## JavaScript

### Canonical patterns

- Chart drawing always registers itself in `chartRegistry` for redraw on tab reveal (M-PAT-03)
- Charts in hidden tabs: call redraw after `classList.add('active')` with 50ms delay
- HTMX requests: check `HX-Request` header and return a partial render, not a full page

### Anti-patterns to flag

- `chart.destroy()` + recreate on every tab switch → use `chartRegistry` redraw instead
- `document.querySelector` for a chart container whose parent can be hidden → add tab-reveal hook
- Inline `<script>` blocks with business logic → move to a static `.js` file

---

## Language & Comments (P-038)

### Rule: new code is always English

| Layer | Language |
|-------|----------|
| Variable / function / class names | EN |
| Comments and docstrings | EN |
| Template filenames, URL slugs | EN |
| UI labels, buttons, messages, `verbose_name` | DE (until P-039 i18n) |

### Anti-patterns to flag

- German variable/function names in files you are touching → translate in the same commit
- German docstrings in files you are touching → translate in the same commit
- Mixed-language file (some EN, some DE comments) → finish the migration
- `# TODO` comments in German → translate

---

## Documentation

Organising principle: status tracking, reference documentation and project
planning stay separate.

### Where things live

| Content | Location |
|---------|----------|
| Project status & backlog | `PROJECTS.md` (index, P-001…P-XXX, TODO → WIP → DONE), `docs/projects/{todo,wip,done}/` (details) |
| User-facing feature docs | `docs/guides/` — how-tos (`EMAIL_IMPLEMENTATION.md`, `CLIENT_TAGGING.md`, `BACKUP_SETUP.md`), setup and configuration |
| Architecture reference | `docs/architecture/` — `CODE_STRUCTURE.md` (modules, patterns), `PERFORMANCE.md` (query optimisation, indexes, N+1); keep current |
| Operational / security | `docs/operations/` |
| Completed project archives | `docs/projects/done/` with date prefix |
| One-off notes & observations | `docs/notes/` — type-checking quirks, contrast issues, status snapshots; no strict format, date-prefix filenames |
| Why something is built the way it is | `docs/decisions/` — ADRs; its README says when one is warranted |
| Generated codebase metrics | `docs/development/` — **never edit by hand**; `scripts/codebase_metrics.py` writes every file in it (LOC by category, file-length distribution and longest files, commit-type mix, release cadence) |
| Historical / superseded docs | `docs/archive/` (`bugfixes/`, `completed/`) with a `YYYY-MM-DD_` or `YYYY-MM_` prefix |

Finer points that decide which of these a file belongs in:

- **`docs/projects/`** holds project *tracking*; technical guides go in
  `docs/guides/` or `docs/operations/`, even when they came out of a project.
- **`docs/operations/`** is for running and maintaining this specific
  installation (`SCRIPTS.md`, `SECURITY.md`, `REINSTALL_CHECKLIST.md`,
  `DPIA.md`) — not user-facing guides, not architecture reference.
- **`docs/architecture/`** is active reference, not an archive:
  `CODE_STRUCTURE.md` and `PERFORMANCE.md` are expected to be current.
- **`docs/development/`** is read, not written: a scheduled workflow pushes a
  refresh branch on the 1st of each month. Read it when deciding whether the
  project needs features or maintenance next.

### Code-Level Documentation (Docstrings)
**Use for**: Function/class behavior, parameters, return values
```python
def calculate_revenue(invoice_items, year=None):
    """
    Calculate total revenue from invoice items.

    Args:
        invoice_items: QuerySet or list of InvoiceItem objects
        year: Optional year filter (int)

    Returns:
        Decimal: Total revenue amount
    """
```

### Inline Comments
**Use sparingly for**:
- Non-obvious business rules
- Edge case handling
- Workarounds (with ticket references)
**Avoid for**:
- Obvious code explanations
- Outdated information (delete instead)

### Anti-patterns to flag

- New feature with no entry in `docs/FEATURES.md`
- Completed project still in `docs/projects/wip/` → graduate to `done/`
- `docs/architecture/CODE_STRUCTURE.md` references a module that no longer exists
- `PROJECTS.md` with more than 2 "Recent Activity" entries → trim oldest
- Docstring missing on a new public function or class

---

## Patterns Reference (M-PAT-01 … M-PAT-08)

Each numbered pattern exists because the bug it prevents is invisible in
review. CLAUDE.md states each rule in one line; this is the worked example,
the failure it came from, and the exact contract.

M-PAT-04 (no inline style blocks, no new `.css` files) stays in CLAUDE.md
§ CSS Architecture — it is a prohibition, not a pattern with an example.
M-PAT-07 and M-PAT-08 have their own contracts under § Templates & CSS above.

### Error Handling Patterns (M-PAT-01)
Use consistent error handling based on context:

```python
# Form Views: Use messages.error() + form_invalid()
from django.contrib import messages

class MyUpdateView(UpdateView):
    def form_invalid(self, form):
        messages.error(self.request, "Bitte korrigieren Sie die Fehler im Formular.")
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        return super().form_invalid(form)

# API Views: Return JsonResponse with appropriate status codes
from django.http import JsonResponse

def api_endpoint(request):
    try:
        # ... processing ...
        return JsonResponse({"success": True, "data": result})
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": "Internal server error"}, status=500)

# Management Commands: Raise exceptions with logging
import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    def handle(self, *args, **options):
        try:
            # ... processing ...
            self.stdout.write(self.style.SUCCESS("Success"))
        except Exception as e:
            logger.error(f"Command failed: {e}")
            raise CommandError(f"Operation failed: {e}")
```

### Date Filter Patterns (M-PAT-02)
Always use RevenueCalculator methods for consistent date filtering:

```python
# Good - Use RevenueCalculator
from my_practice.utils import RevenueCalculator
year_stats = RevenueCalculator.get_year_revenue(
    2026,
    use_paid_date=True,  # Use invoice.paid_date instead of invoice_date
    practice=request.current_practice,
)
revenue = year_stats["total"]

# Avoid - Manual filter building
# invoice_qs = Invoice.objects.filter(invoice_date__year=year, status='paid')
```

### Chart Rendering in Hidden Tabs (M-PAT-03)
Charts rendered in hidden tabs (display: none) get incorrect dimensions because container.clientHeight returns 0.

```javascript
// Problem: Chart in hidden tab has zero height
.tab-content { display: none; }  // container.clientHeight = 0

// Solution: Redraw charts when tab becomes visible
function switchTab(tabName) {
    // Show tab first
    document.getElementById(tabName + '-tab').classList.add('active');

    // Redraw charts after small delay (DOM must be visible)
    setTimeout(function() {
        const canvases = document.querySelectorAll(`#${tabName}-tab canvas`);
        canvases.forEach(canvas => {
            if (chartRegistry[canvas.id]) {
                const ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                chartRegistry[canvas.id](canvas);  // Redraw with correct dimensions
            }
        });
    }, 50);
}

// Also redraw on initial load if non-default tab is active
```

**Key Points**:
- Charts use `container.clientHeight` for sizing
- Hidden containers return 0 → canvas gets wrong dimensions
- Always redraw charts after tab visibility changes
- Use 50-100ms delay to ensure DOM is rendered
- Leverage `chartRegistry` from chart_core.js for redraws

### Form Draft Guard (M-PAT-06)
Long-text forms (session logs, case notes) lose typed content if the user accidentally navigates away (e.g. Alt+Left/Right browser back/forward) before submitting. `app/static/js/form_draft_guard.js` is a reusable, opt-in guard loaded globally in `base.html` (like `widgets.js`) — no per-template `extra_js` needed.

```html
<form method="post" action="..." id="my-form"
      data-draft-guard
      data-draft-message="{% trans "You have an unsaved draft from an earlier attempt." %}"
      data-draft-restore-label="{% trans "Restore draft" %}"
      data-draft-discard-label="{% trans "Discard" %}">
    {% csrf_token %}
    ...
</form>
```

**Key Points**:
- Opt in per form with `data-draft-guard` — a stable `id` on the form keeps drafts scoped correctly if a page ever has more than one guarded form
- Autosaves all named fields (text/textarea/select/checkbox/radio) to `localStorage` on input/change (debounced), keyed by URL path + form id
- Offers a restore-or-discard banner (`.draft-restore-banner` in `tailwind.css`) on page load if a draft exists
- Warns via the native `beforeunload` dialog while the form is dirty and unsubmitted
- Clears the draft on successful submit
- The three `data-draft-*` label strings are reused verbatim across forms (see `session_log_form.html`, `client_detail.html`) — reuse the same msgids rather than minting new ones
- Emits a bubbling `draftguard:dirty` CustomEvent on the form whenever its dirty state flips, with `event.detail.dirty` as a boolean. Use it when the form can be scrolled or tabbed out of view, since `beforeunload` alone can't tell the user *where* the unsaved edit is. `client_detail.html` listens for it and toggles `.page-tab-btn--dirty` (a dot indicator, `tailwind.css`) plus a "Unsaved changes" `title` on the owning tab button:

```javascript
document.addEventListener('draftguard:dirty', function (e) {
    const tabContent = e.target.closest('.page-tab-content');
    if (!tabContent) return;
    const btn = document.querySelector('.page-tab-btn[data-tab="' + tabContent.id.replace('ptab-', '') + '"]');
    if (btn) btn.classList.toggle('page-tab-btn--dirty', e.detail.dirty);
});
```

### Working-Day Calculations (M-PAT-05)

**Rule: Always use `DateRangeHelper.count_working_days` with Berlin public holidays. Never use the `round(days * 5/7)` calendar approximation.**

The `5/7` approximation diverges badly on holiday-heavy periods (Easter, Christmas), producing materially wrong utilisation figures.

```python
from my_practice.utils.date_helpers import DateRangeHelper
from my_practice.utils.practice_days import berlin_public_holidays

# Build the holiday set once, covering all years in the date range
holidays: set[date] = set()
for yr in range(start_date.year, end_date.year + 1):
    holidays |= berlin_public_holidays(yr)

# Then pass it to every working-day count in the function
days = DateRangeHelper.count_working_days(start, end, holidays)
```

**Key points:**
- `count_working_days(start, end)` — inclusive both ends, Mon–Fri only (no holidays). Safe for callers that don't need holidays.
- `count_working_days(start, end, holidays)` — same but also excludes the given holiday dates.
- Build the holiday set **once per function call**, not inside a loop.
- For "days elapsed before a milestone" (half-open `[start, end)`): pass `end - timedelta(days=1)` as the end argument so that a same-day event counts as 0 elapsed days.
- `berlin_public_holidays(year)` lives in `utils/practice_days.py` and is NOT re-exported from `utils/__init__.py` — import it directly.

---

## Repository Tooling & Guardrails

### One hook mechanism

`.pre-commit-config.yaml` is the only one. Install it with `./dev.py
install-hooks` (which needs the host `pre-commit`, pinned in
`app/requirements-dev.txt`).

There used to be a second mechanism — a committed `.githooks/pre-commit`
installed by pointing `core.hooksPath` at it. The two silently disabled each
other: `core.hooksPath` overrides `.git/hooks/` wholesale, so whichever was
installed last turned the other off with no output saying so, and the gitleaks
secret scan was the usual casualty. Do not add a second mechanism back.

CI runs `pre-commit run --all-files`, so a clone that never installed the hooks
is still covered — but the feedback arrives on the PR instead of at `git
commit`.

**`SKIP=gitleaks` in CI is deliberate.** The gitleaks hook is `gitleaks protect
--staged`, which scans the git *index*. Under `--all-files` nothing is staged,
so it reports a pass without looking at anything. A separate CI step runs
`gitleaks detect` over the full history instead; it reads the version out of
`.pre-commit-config.yaml` so there is one gitleaks version in the repo rather
than two that can drift.

### Files that duplicate content on purpose

Two pairs, each with a checker, because no linter has an opinion about
cross-file duplication:

| Pair | Why duplicated | Checker |
| --- | --- | --- |
| `dev.py` ↔ `prod.py` | `prod.py` ships as a single stdlib-only file and cannot import a shared module | `scripts/check_shared_helpers.py` |
| `app/requirements.txt` ↔ `app/requirements-dev.txt` | Dependabot does not resolve `-r` includes when raising a security-update PR | `scripts/check_requirements_sync.py` |

The requirements pair had already drifted before the checker existed:
`requirements.txt` pinned `sqlparse` to close PYSEC-2026-3696..3699 and
`requirements-dev.txt` — the file CI installs — did not carry the pin, so the
suite ran against the vulnerable version the production image did not ship.

Both run in the pre-commit hooks, in `./dev.py quality`, and in CI.

### Type checking (mypy)

`app/mypy.ini` has had a per-module strictness ladder since it was written, but
nothing ever ran it, so "typed" meant whatever survived review. CI now runs it
over exactly the modules the ladder declares strict:

```
mypy --follow-imports=silent \
  my_practice/models \
  my_practice/utils/calculations.py \
  my_practice/utils/date_helpers.py \
  my_practice/utils/invoice_helpers.py \
  my_practice/utils/revenue_helpers.py
```

`--follow-imports=silent` keeps the gate on those modules rather than failing
on errors in everything they happen to import (133 errors across 34 files
without it, 0 with it). Widen the path list as more of the tree is annotated —
and widen `mypy.ini`'s `disallow_untyped_defs` overrides in the same commit, so
the two never disagree about what "strict" covers.

`warn_unused_ignores = True` is on, so a `# type: ignore[...]` that stops being
necessary becomes an error rather than quiet cruft. The ones in `models/` mark
a single django-stubs limitation: a set FK id (`self.session_id`) does not
narrow the FK object (`self.session`) to non-`None`.

### Guardrail tests

Ratchets that encode a contract review cannot see. Shrink the allowlists, never
grow them.

| Test | Contract |
| --- | --- |
| `test_i18n_coverage.py` | Templates wrapped, no German msgids, no fuzzy `.po` entries (P-039) |
| `test_css_tokens.py` | No undefined `var(--x)`, no new hardcoded hex on semantic classes (M-PAT-07) |
| `test_privacy_coverage.py` | Personal fields blurred, non-personal fields not (M-PAT-08) |
| `test_code_language_policy.py` | English identifiers and comments (P-038) |
| `test_release_guardrails.py` | No model change without its migration; the three version strings agree |

`test_release_guardrails.py` covers the two failure modes that only surface
after the fact: the suite builds its schema from the models, so a missing
migration stays green until `migrate` runs against a real database; and
`version.py` / `prod.py` / `docker-compose.prod.yml` drifting apart is what
makes `./prod.py update` behave surprisingly.

### What CI checks that a local run does not

- `gitleaks detect` over the full git history.
- `manage.py check --deploy --fail-level WARNING` against the hardened
  configuration (`DJANGO_DEBUG=False`, `SECURE_SSL_REDIRECT=true`). The suite
  runs with `DJANGO_DEBUG=True`, so the entire `if not DEBUG:` block in
  `config/settings.py` — every security header, cookie and HSTS setting — is
  otherwise never evaluated by anything.
- `shellcheck -S warning scripts/*.sh`.

---

## Scan Checklist (use alongside `./dev.py review`)

Copy this block when starting a manual review pass:

```
Queries & data access
[ ] Any inline Revenue/Invoice filter logic that should use a helper?
[ ] N+1 queries? (look for loops calling .all() on a related manager)
[ ] Missing select_related / prefetch_related?
[ ] Working-day calc using 5/7 approximation?

Views
[ ] New views bypassing PracticeScopedXxxView mixins?
[ ] edit/delete views missing next= support?
[ ] Absolute imports (my_practice.X) in view files?

Models
[ ] New model missing TimestampedModel?
[ ] Old-style type hints (Optional, List, Dict)?

Templates & CSS
[ ] Bare <style> blocks in non-PDF templates?
[ ] Hardcoded colours or inline styles?
[ ] Privacy-mode coverage — now automated by `test_privacy_coverage.py` (M-PAT-08)

Language
[ ] German names/comments in touched files?
[ ] Mixed-language file (half migrated)?

Documentation
[ ] Completed project still in wip/?
[ ] PROJECTS.md > 2 Recent Activity entries?
[ ] CODE_STRUCTURE.md still accurate?
[ ] New public functions missing docstrings?
```

---

## Periodic Review Cadence

Larger-scale health checks to keep the codebase fresh and consolidated.
Run `./dev.py review` for the automated parts, then work through the manual checklist.
The scan checklist below is the manual half.

### Monthly (~45 min)

**Automated** (`./dev.py review`):
- Dead code: unused imports, functions, variables (vulture + ruff F401/F841)
- Dependency security: known CVEs (pip-audit)
- Outdated packages: patch/minor version drift (pip list --outdated)
- Test coverage: uncovered lines in views and models (coverage report)

**Manual**:
- [ ] Scan git log for repeated fixes in the same area — sign of a design problem
- [ ] Check for German comments/identifiers in recently touched files (P-038)
- [ ] GH issues: close stale items older than ~2 months with no activity
- [ ] Any new views bypassing mixins/builders? Consolidate if so

### Quarterly (~2-3h)

**Automated** (`./dev.py review --full`):
- Everything in the monthly run, plus:
- Complexity hotspots: functions over 50 lines or cyclomatic complexity > 10 (radon)
- Long files: every app/test/template/JS file of 500+ lines (`scripts/codebase_metrics.py --largest`; the trend lives in `docs/development/`)
- Dead CSS selectors: `npx purgecss --css app/static/css/tailwind.out.css --content "app/templates/**/*.html" "app/static/js/**/*.js" --output /tmp/purged/` then diff vs `/tmp/purged/tailwind.out.css`. Watch for false positives from dynamically-built class names (e.g. `class="billing-row--{{ row.status }}"` — those classes are real even if purgecss can't see them).

**Manual**:
- [ ] Duplication scan: look for similar blocks across views/utils — extract a helper
- [ ] Dependency major versions: check Django, Python, WeasyPrint, psycopg release notes
- [ ] Pattern audit: are new utils/views following the established builder/helper patterns?
- [ ] Archive PROJECTS.md: move stale WIPs to done/cancelled, keep backlog honest
- [ ] docs/architecture/CODE_STRUCTURE.md: still accurate? Update if not
- [ ] New Django/Python features available that simplify existing code?
