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
| Client map (code → object) | `build_client_map()` — uses `.only()`, no N+1 |
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

### Dark-mode contract (M-PAT-06)

Every CSS rule that sets `background` to a themed variable must also set an explicit `color`. Omitting `color` causes dark-on-dark text when the background goes dark but the inherited text colour doesn't follow.

```css
/* Good */
.my-card {
    background: var(--card-bg);
    color: var(--text-primary);
}

/* Bad — text colour is unspecified; breaks in dark mode */
.my-card {
    background: var(--card-bg);
}
```

Links inside themed containers must scope a link-colour rule so they use the theme token rather than the browser default (`#0000ee`, invisible on dark backgrounds):

```css
.my-container {
    background: var(--bg-secondary);
    color: var(--text-primary);

    a { color: var(--link-color); }
}
```

Note: a global `a { color: var(--color-link); }` rule in `@layer base` in `tailwind.css` handles the base case. You only need the scoped rule when the container overrides `color` to something that would make the global rule look wrong (e.g. white text on a coloured background where links should also be white).

### Anti-patterns to flag

- `<style>` block inside a template `{% block extra_css %}` → move to `@layer components` in `tailwind.css`
- New `.css` file created for a page → move into `tailwind.css @layer components` instead
- `attrs={"class": "form-control"}` on form fields → use `StyledFormMixin`
- Inline `style="..."` on elements that should use CSS classes → replace with class
- Hardcoded colours (`#2d3748`, `#a5b4fc`) in templates or CSS → use `var(--color-*)` tokens
- `background: var(--*)` without a matching `color:` rule → dark-on-dark regression risk (M-PAT-06)
- `.text-success` / `.text-warning` / `.text-danger` / `.text-info` are now tokenised — don't add hardcoded hex equivalents
- `{{ client.full_name }}` without `sensitive-data` class outside of clearly staff-only sections
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

### Where things live

| Content | Location |
|---------|----------|
| Project status & backlog | `PROJECTS.md` (index), `docs/projects/{todo,wip,done}/` (details) |
| User-facing feature docs | `docs/guides/` |
| Architecture reference | `docs/architecture/` — keep current |
| Operational / security | `docs/operations/` |
| Completed project archives | `docs/projects/done/` with date prefix |
| One-off notes & observations | `docs/notes/` |

### Anti-patterns to flag

- New feature with no entry in `docs/FEATURES.md`
- Completed project still in `docs/projects/wip/` → graduate to `done/`
- `docs/architecture/CODE_STRUCTURE.md` references a module that no longer exists
- `PROJECTS.md` with more than 2 "Recent Activity" entries → trim oldest
- Docstring missing on a new public function or class

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
[ ] client.full_name without sensitive-data class?

Language
[ ] German names/comments in touched files?
[ ] Mixed-language file (half migrated)?

Documentation
[ ] Completed project still in wip/?
[ ] PROJECTS.md > 2 Recent Activity entries?
[ ] CODE_STRUCTURE.md still accurate?
[ ] New public functions missing docstrings?
```
