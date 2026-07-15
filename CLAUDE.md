# Project Instructions

Therapy practice payment/invoicing system built with Django, PostgreSQL, running in Docker.

## 🔒 Privacy & Data Protection (CRITICAL)

**Ground Rules - NEVER violate these:**
1. **No Real Names**: Use dummy names in all docs, code, examples, commit messages
   - ✅ Good: "Max Mustermann", "Anna Schmidt", "Maria Musterfrau"
   - ❌ Bad: Any real client or practitioner names
2. **No Contact Info**: Never include real emails, phone numbers, addresses
   - ✅ Good: "mail@example.com", "contact@practice.example", "+49 123 456789"
   - ❌ Bad: Real email addresses or phone numbers
3. **Anonymized Examples**: Use fictional data in documentation and tests
   - Client codes: XX-1, YY-2, AB-3
   - Invoice numbers: INV-001, INV-002
   - Bank names: "M. Schmidt", "Test GmbH"
4. **Review Before Commit**: Check for leaked PII in:
   - Commit messages
   - Documentation files
   - Code comments
   - Test fixtures
   - Migration defaults (use placeholders)

**Client Privacy Mode** (active by default):
- Templates use `client.client_code` instead of full names
- Admin interface respects privacy settings
- Exports use codes unless explicitly needed

## Current Focus (Q2 2026)
- Django i18n bilingual UI (P-039): scaffold ✅, language switcher ✅, template wrapping in progress

### i18n Conventions (P-039)
- **English as msgids**: `{% trans "Switch" %}` not `{% trans "Wechseln" %}`. German text lives in `locale/de/django.po` as `msgstr`.
- **Any template touched for any reason must be fully wrapped** with `{% load i18n %}` and `{% trans %}`/`{% blocktrans %}` in the same commit. PDF templates (`invoice_pdf_*.html`, `treatment_contract_pdf.html`, `intake_form_pdf.html`) are exempt — they handle language per-document, not via Django i18n.
- **Any Python file touched for any reason must have its user-facing strings wrapped** with `gettext_lazy as _` (for module-level/class attributes) or `gettext as _` (for function-scope strings). User-facing means: `messages.*()` calls, `JsonResponse` error/success values, form error strings. Skip if the file has no user-facing strings at all. Skip if wrapping would require a large structural refactor (e.g. deeply nested f-strings across many functions) — note it in the PR instead.
- After changing templates, run `./dev.py i18n` to extract + compile.

See [PROJECTS.md](../PROJECTS.md) for numbered projects with status tracking (TODO/WIP/DONE).

## Development Commands (use `./dev.py` for everything)
```bash
./dev.py start              # Start containers
./dev.py test               # Run Django + JS tests
./dev.py test my_practice.tests.test_calculations  # Specific test
./dev.py shell              # Django shell (interactive)
./dev.py manage <cmd>       # Django management commands
./dev.py run <script.py>    # Run script with Django environment
./dev.py logs -f            # Follow container logs
./dev.py restart --force    # Full restart (reloads .env)
./dev.py lint               # Run ruff format + ruff lint only (fast, no tests)
./dev.py quality            # Run lint + Tailwind CSS build + full test suite (pre-release)
./dev.py i18n               # Extract + compile translation strings
./dev.py smoke [vX.Y.Z]     # Boot a released GHCR image with throwaway DB, verify, tear down
```

### Git workflow
**`main` is branch-protected — all changes require a PR**, even trivial ones like generated files or docs. Always work on a feature branch and open a PR via `gh pr create`.

### Release process
Full checklist: [docs/operations/RELEASE.md](docs/operations/RELEASE.md). Summary:

1. **Open a version-bump PR** — bump all three version strings (they must match) plus the docs pass, same as any other change (branch-protected `main`):
   - `app/my_practice/version.py` — `VERSION = "vX.Y.Z"`
   - `prod.py` — `VERSION = "vX.Y.Z"`
   - `docker-compose.prod.yml` — `image: ghcr.io/dholbach/my-practice:vX.Y.Z`
   - Docs pass: `docs/CHANGELOG.md`, `docs/FEATURES.md`, `PROJECTS.md`
2. **Merge PR**, then tag and create a GitHub release with real highlights (not just a pointer to CHANGELOG.md — required for `./prod.py update`):
   ```bash
   git tag vX.Y.Z && git push origin vX.Y.Z
   gh release create vX.Y.Z --title "vX.Y.Z" --notes "<highlights pulled from docs/CHANGELOG.md>"
   ```

### Testing Strategy

Match test scope to change scope — don't run the full suite for every edit:

- **During development**: run only the test file(s) for code you touched
  ```bash
  ./dev.py test my_practice.tests.test_inquiry
  ./dev.py test my_practice.tests.test_invoice my_practice.tests.test_calculations
  ```
- **Before committing**: broaden slightly to cover shared code touched (models, utils)
- **Full suite** (`./dev.py test`): once per session when work is done, or before a release

If you touch a shared utility or model used across many views, run a wider set. If you touch one view/form, run its test file.

## Architecture

### Modular Structure
- **Models** (`app/my_practice/models/`): Domain-focused modules (client, invoice, practice, financial, etc.)
- **Views** (`app/my_practice/views/`): Feature-specific view modules + CRUD mixins
- **Utils** (`app/my_practice/utils/`): Reusable business logic - **USE THESE FIRST!**
- **Templates** (`app/templates/`): Base template + `includes/` for reusable components

### Essential Patterns (Use These!)

#### Builder Classes for Complex Context
When views need complex context preparation, use builder classes:
```python
# Financial lists (expenses, withdrawals)
from my_practice.utils import FinancialListContextBuilder
builder = FinancialListContextBuilder(queryset, year_filter=year)
context, items = builder.build_context(include_categories=True, include_tax_deductible=True)

# Analytics dashboard
from my_practice.utils import AnalyticsDashboardBuilder
builder = AnalyticsDashboardBuilder(start_date, end_date)
context = builder.build_context()

```

#### Filter Helpers for QuerySets
Encapsulate complex filtering logic:
```python
from my_practice.utils import InvoiceFilterHelper
helper = InvoiceFilterHelper(Invoice.objects.all())
filtered = helper.apply_filters(
    search_query=request.GET.get('search'),
    year_filter=year,
    status_filter=status
)
```

#### Session Counting - Always use centralized function
```python
from my_practice.utils import count_sessions
sessions = count_sessions(invoice.items.all())  # Formula: (duration / 60.0) * quantity
```

#### CRUD Views - Use mixins from `views/crud_mixins.py`
```python
# Simple form-based CRUD
class ExpenseCreateView(PracticeScopedCreateView):
    model = CompanyExpense
    form_class = CompanyExpenseForm
    template_name = "my_practice/expense_form.html"
    success_url = reverse_lazy("expense_list")
    success_message = "Ausgabe vom {obj.date:%d.%m.%Y} erfolgreich erstellt."

# ?next= redirect support (success_url honors ?next=, exposes context["next"])
class ExpenseDeleteView(NextRedirectMixin, PracticeScopedDeleteView):
    model = CompanyExpense
    success_url = reverse_lazy("expense_list")

# Invoice formsets
class InvoiceCreateView(InvoiceFormsetMixin, PracticeScopedCreateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return self.get_formset_context(context, formset_key="items")
```
Available base classes: `PracticeScopedListView`, `PracticeScopedCreateView`, `PracticeScopedUpdateView`, `PracticeScopedDeleteView`, `NextRedirectMixin`, `InvoiceFormsetMixin`.

#### Centralized Queries and Calculations
```python
# Revenue calculations
from my_practice.utils import RevenueCalculator
revenue = RevenueCalculator.get_total_revenue(year=2026, status='paid')
breakdown = RevenueCalculator.get_status_breakdown(year=2026)

# Date ranges
from my_practice.utils import DateRangeHelper
helper = DateRangeHelper(start_date, end_date)
months = helper.get_month_list()

# Client helpers
from my_practice.utils import build_client_map
client_map = build_client_map()  # Optimized with .only()
```

#### Error Handling Patterns (M-PAT-01)
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

#### Date Filter Patterns (M-PAT-02)
Always use RevenueCalculator methods for consistent date filtering:

```python
# Good - Use RevenueCalculator
from my_practice.utils import RevenueCalculator
revenue = RevenueCalculator.get_total_revenue(
    year=2026,
    status='paid',
    use_paid_date=True,  # Use invoice.paid_date instead of invoice_date
    practice=request.current_practice
)

# Avoid - Manual filter building
# invoice_qs = Invoice.objects.filter(invoice_date__year=year, status='paid')
```

#### Chart Rendering in Hidden Tabs (M-PAT-03)
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

## Code Style & Patterns

### Import Organization
Use relative imports for app-internal code:
```python
# Good
from ..models import Client, Invoice
from ..utils import count_sessions, RevenueCalculator
from .crud_mixins import PracticeScopedCreateView

# Avoid
from my_practice.models import Client
```

### Error Handling Patterns
- **Form Views**: Use `messages.error()` + `form_invalid()` pattern
- **API Views**: Return `JsonResponse` with appropriate status codes
- **Management Commands**: Raise exceptions with logging

### Query Optimization
- Always use `.select_related()` for ForeignKey access: `Invoice.objects.select_related('client')`
- Use `.prefetch_related()` for reverse relations: `Client.objects.prefetch_related('invoices')`
- Use `.only()` when building maps: `Client.objects.only('id', 'client_code', 'full_name')`

## Language Policy (P-038)

| Layer | Language | Notes |
|-------|----------|-------|
| Code — variable/function/class names | **EN** | Always |
| Code — comments and docstrings | **EN** | Always; migrate German ones as you touch them |
| Filenames (templates, CSS, JS, scripts) | **EN** | Always; rename German ones as you touch them |
| URL slugs | **EN** | Always; 4 German slugs remain (tracked in P-038) |
| Docs (.md files, guides, architecture) | **EN** | Always; migrate German docs as you touch them |
| UI/app text (labels, buttons, messages, verbose_names) | **DE** | Until P-039 (Django i18n); keep German for now |
| model `verbose_name` / `help_text` | **DE** | Deferred to P-039 — do not Anglicise individually |

**Practical rule for day-to-day work:** new code is always English. When editing a file that has German comments or German-named identifiers, translate them in the same commit — don't leave a file half-migrated.

## Conventions
- **UI Language**: German for all user-facing text (buttons, labels, page titles, messages); see Language Policy above
- **Currency Format**: German standard with non-breaking space ("2680 €")
- **Code Style**: Black formatting, isort for imports
- **Tests**: Place in `tests/test_<module>.py`, use Django TestCase
- **Client Privacy**: Always use client codes in templates, respect privacy mode
- **Type Hints**: Use Python 3.13 union syntax: `str | None`, `dict[str, int]`, `list[str]` (not `Optional`, `Dict`, `List`)
- **No dead code**: Never leave commented-out code blocks; delete unused code

## CSS Architecture (M-PAT-04)

**Rule: No inline `<style>` blocks in templates and no new `.css` files — all CSS belongs in `tailwind.css`.**

### Structure
- `app/static/css/tailwind.css` — single source file; compiled to `tailwind.out.css` by `@tailwindcss/cli`
- `app/static/css/tailwind.out.css` — compiled output, loaded by `base.html` (gitignored; rebuilt by `npm run build:css`)
- PDF templates (`invoice_pdf_*.html`) are exempt — they require inline styles for PDF rendering

### Adding new styles
Put new component classes in `tailwind.css` under `@layer components`:
```css
/* in tailwind.css */
@layer components {
  .my-component { background: var(--color-surface); color: var(--color-text-primary); }
}
```

Use `--color-*` tokens for all colours — they automatically adapt to dark mode via `[data-theme="dark"]` overrides. Never use hardcoded hex values.

Do **not** create a new `.css` file. Do **not** add `{% block extra_css %}` link tags for page-specific CSS.

Never add bare `<style>` blocks:
```html
{# BAD — do not do this #}
{% block extra_css %}
<style>
    .my-class { ... }
</style>
{% endblock %}
```

### Forms
- Use `StyledFormMixin` for all ModelForms — no manual `attrs={"class": "form-control"}` on field widgets
- Use `DateFormField` for all date inputs — handles `date` input type automatically

### Delete Views
- Use `PracticeScopedDeleteView` for all delete views — no wrapper functions or custom `get_object()`

### Models
- Use `TimestampedModel` as base class for all new models needing `created_at`/`updated_at`

## Key Models
- `Client` - Therapy clients with individual hourly rates
- `Invoice` / `InvoiceItem` - Invoices with line items (duration, quantity, rate) - **primary data source**
- `Practice` - Practice settings (logo, signature, bank details, email templates)
- `CompanyWithdrawal` / `CompanyExpense` - Financial tracking

## Database
PostgreSQL with performance indexes (see migrations 0013, 0014). Use `select_related`/`prefetch_related` for related data.

## File Organization
When adding new features:
1. **Check `utils/` first** - Many helpers already exist!
2. Model → `models/<domain>.py` + update `models/__init__.py`
3. View → `views/<feature>_views.py` + update `views/__init__.py`
4. Utility functions → `utils/<purpose>.py` + update `utils/__init__.py`
5. Tests → `tests/test_<module>.py`

## Documentation Guidelines

### Documentation Structure Pattern

**Organization Principle**: Clear separation between status tracking, reference documentation, and project planning.

#### PROJECTS.md (Root) - Project Index
**Use for**:
- Central index of all projects (P-001 to P-XXX)
- Status tracking: TODO → WIP → DONE
- Cross-references to detailed project docs
- Project metrics and priorities

#### docs/projects/{todo,wip,done}/ - Project Documentation
**Use for**:
- Detailed project documentation with P-XXX numbering
- Project-specific tasks, timelines, and decisions
- Cross-referenced from PROJECTS.md
- **Pattern**: Project tracking lives here, technical guides live in docs/guides/ or docs/operations/

#### docs/guides/ - User Guides
**Use for**:
- User-facing how-to guides (EMAIL_IMPLEMENTATION.md, CLIENT_TAGGING.md, BACKUP_SETUP.md)
- Feature usage documentation
- Setup and configuration guides

#### docs/architecture/ - Architecture Reference
**Use for**:
- CODE_STRUCTURE.md - Current architecture, patterns, module organization
- PERFORMANCE.md - Query optimization, indexes, N+1 solutions
- Active reference documentation (NOT archived)

#### docs/operations/ - Housekeeping
**Use for**:
- SCRIPTS.md, SECURITY.md — running and maintaining this specific installation
- REINSTALL_CHECKLIST.md, DPIA.md — operational and compliance docs
- Not for user-facing guides; not for architecture reference

#### docs/notes/ - Random Notes
**Use for**:
- One-off analyses, workarounds, observations that don't fit elsewhere
- Type-checking quirks, contrast issues, status snapshots
- No strict format required; date-prefix filenames recommended

#### docs/archive/ - Historical Documentation
**Use for**:
- Completed projects and refactorings (with dates: 2025-12-23_IMPROVEMENTS.md)
- Historical analyses and planning documents
- Subdirectories: bugfixes/, completed/
- **Date format**: YYYY-MM-DD_ or YYYY-MM_ prefix

#### Code-Level Documentation (Docstrings)
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

#### Inline Comments
**Use sparingly for**:
- Non-obvious business rules
- Edge case handling
- Workarounds (with ticket references)
**Avoid for**:
- Obvious code explanations
- Outdated information (delete instead)

### Documentation Principles
1. **One source of truth per topic** - PROJECTS.md is the index, P-XXX docs have details
2. **Status-based organization** - Use todo/wip/done directories for lifecycle tracking
3. **Numbered projects** - P-XXX format for easy cross-referencing
4. **Docstrings are mandatory** for public functions/classes
5. **Code is the primary documentation** - write self-documenting code
6. **Comments explain WHY, not WHAT** - code shows what, comments explain reasoning
7. **Update docs with code changes** - outdated docs are worse than no docs
8. **Link between docs** - use relative links to connect related documentation
9. **Archive with dates** - Historical docs get YYYY-MM-DD_ prefixes

## Working-Day Calculations (M-PAT-05)

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

## Available Utility Classes (Use Before Creating New Code!)
- `AnalyticsDashboardBuilder` - Dashboard context preparation
- `FinancialListContextBuilder` - Financial list views
- `InvoiceFilterHelper` - Invoice queryset filtering
- `RevenueCalculator` - All revenue calculations
- `DateRangeHelper` - Date range utilities
- `build_client_map()` - Optimized client code→client mapping

See [docs/architecture/CODE_STRUCTURE.md](docs/architecture/CODE_STRUCTURE.md) for complete reference.

## Documentation Gardening

At the end of each coding session, do a quick gardening pass before committing.

### Done-Item Graduation Workflow
1. **User-facing features** → add a one-line entry to `docs/FEATURES.md` under the relevant section
2. **Technical changes** → already captured by CHANGELOG.md commit entries; no extra action needed
3. **Project completion** → create `docs/projects/done/P-XXX_NAME.md` (if it doesn't exist), move the project doc from `wip/` or `todo/` to `done/`, add a brief "Recent Activity" entry to PROJECTS.md, and mark the row in the PROJECTS.md "Abgeschlossen" table

### Keeping PROJECTS.md Clean
- Keep at most **2 "Recent Activity" entries** (the last two sessions only)
- Older entries belong in CHANGELOG.md — delete them from PROJECTS.md after adding a new one
- The Backlog section should contain only open/upcoming work; remove items once done

### Gardening Checklist (end of each session)
- [ ] PROJECTS.md: add new "Recent Activity" entry, drop oldest if >2 exist
- [ ] docs/FEATURES.md: add user-facing highlights
- [ ] docs/projects/done/: create/update P-XXX doc for completed projects

## Periodic Review

Larger-scale health checks to keep the codebase fresh and consolidated.
Run `./dev.py review` for the automated parts, then work through the manual checklist.
Full scan checklist and canonical patterns: [docs/guides/CODEBASE_STANDARDS.md](docs/guides/CODEBASE_STANDARDS.md)

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
- Dead CSS selectors: `npx purgecss --css app/static/css/tailwind.out.css --content "app/templates/**/*.html" "app/static/js/**/*.js" --output /tmp/purged/` then diff vs `/tmp/purged/tailwind.out.css`. Watch for false positives from dynamically-built class names (e.g. `class="billing-row--{{ row.status }}"` — those classes are real even if purgecss can't see them).

**Manual**:
- [ ] Duplication scan: look for similar blocks across views/utils — extract a helper
- [ ] Dependency major versions: check Django, Python, WeasyPrint, psycopg release notes
- [ ] Pattern audit: are new utils/views following the established builder/helper patterns?
- [ ] Archive PROJECTS.md: move stale WIPs to done/cancelled, keep backlog honest
- [ ] docs/architecture/CODE_STRUCTURE.md: still accurate? Update if not
- [ ] New Django/Python features available that simplify existing code?
