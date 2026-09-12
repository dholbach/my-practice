# P-000: Code Quality Pass (Jan–Feb 2026)

**Status**: ✅ DONE
**Completed**: 1 Feb 2026

## What Was Done

An early code-quality review of the (then much smaller) codebase found 15 issues
across duplication, complexity, missing query optimization, dead code, and
inconsistent patterns. All 15 were resolved. The lasting results, still in the
codebase today:

- **`AnalyticsDashboardBuilder`** (`utils/analytics_dashboard_builder.py`) —
  extracted from a 223-line `analytics_dashboard()` view
- **`InvoiceFilterHelper`** (`utils/invoice_filter_helper.py`) — extracted from
  a long `InvoiceListView.get_queryset()`
- **`FinancialListContextBuilder`** (`utils/financial_list_context_builder.py`)
  — de-duplicated expense/withdrawal list context building
- **`InvoiceFormsetMixin`** (`views/crud_mixins.py`) — de-duplicated invoice
  formset handling
- The error-handling and date-filter patterns from this pass (messages.error +
  form_invalid for forms, JsonResponse for APIs, `RevenueCalculator` for all
  date-based revenue filtering) are now standing conventions — see CLAUDE.md's
  "Error Handling Patterns" and "Date Filter Patterns" sections
- `PracticeAnalyzer._analyze_client()` was split into focused helper methods

**No longer relevant**: this review's single biggest item, extracting a
520-line CSV `import_invoices()` view into an `InvoiceCSVImporter` class, was
later removed entirely — that CSV invoice-import feature doesn't exist in the
current codebase (superseded by other invoicing workflows). The class and its
originating view are gone; only the pattern it established (builder classes
for complex context, listed above) survived and generalized.

## Related

- [CODE_STRUCTURE.md](../../architecture/CODE_STRUCTURE.md) — current architecture
- [CLAUDE.md](../../../CLAUDE.md) — "Essential Patterns" and error/date-filter conventions
