# my_practice — Code Structure

**Last updated: 2026-06-15** (reflects current codebase; module descriptions below are from the original Jan 2026 refactor — see source files for full detail)

## Overview

The application was refactored from a monolithic `views.py` (1480 lines) into a modular structure with clear separation of concerns.

## Directory Structure

```
app/my_practice/
├── models/                     # Domain models package (17 modules)
│   ├── __init__.py            # Package exports with __all__
│   ├── base.py                # TimestampedModel base class
│   ├── bank_statement.py      # Bank statement + transactions
│   ├── calendar.py            # Google Calendar tokens
│   ├── client.py              # Client management
│   ├── client_alias.py        # Client alias / search name
│   ├── clinical.py            # ClientProfile, SessionLog, SupervisionItem, ClientNote
│   ├── financial.py           # CompanyWithdrawal & CompanyExpense
│   ├── inquiry.py             # ClientInquiry lead tracking
│   ├── invoice.py             # Invoice & InvoiceItem
│   ├── operational.py         # OperationalChecklist + items
│   ├── practice.py            # Practice + UserPractice
│   ├── service.py             # ServiceType
│   ├── session.py             # Session
│   ├── tag.py                 # ClientTag + ClientTagAssignment
│   ├── timeoff.py             # TimeOff tracking
│   └── todo.py                # PracticeTodo
│
├── views/                      # View modules
│   ├── __init__.py            # Central exports for all views
│   ├── crud_mixins.py         # PracticeScopedCreateView/UpdateView/DeleteView/ListView
│   ├── analytics_views.py     # Analytics & reports
│   ├── api_views.py           # JSON API endpoints + PDF generation
│   ├── bank_import_views.py   # Bank statement CSV import
│   ├── batch_invoice_views.py # Monthly batch invoice creation
│   ├── calendar_views.py      # Google Calendar sync + session import
│   ├── client_views.py        # Client list, detail, intake
│   ├── clinical_views.py      # ClientProfile, SessionLog, SupervisionItem, triage
│   ├── dashboard_views.py     # Dashboard & home
│   ├── email_views.py         # Email compose + send
│   ├── expense_views.py       # Expense CRUD + list
│   ├── import_views/          # CSV import package (invoices, sessions)
│   ├── inquiry_views.py       # Lead tracking + funnel analytics (P-031/P-034/P-037)
│   ├── invoice_views.py       # Invoice CRUD + formset
│   ├── operational_views.py   # Operational checklist widget
│   ├── practice_views.py      # Practice settings + multi-practice management
│   ├── search_views.py        # Global search
│   ├── tag_views.py           # Client tag management
│   ├── tax_views.py           # Tax year summary + workday audit
│   ├── todo_views.py          # Practice todo list
│   └── withdrawal_views.py    # Withdrawal CRUD + list
│
├── utils/                      # Utility functions (34 modules)
│   ├── __init__.py            # Central exports
│   ├── agenda_helpers.py      # Session agenda / queue helpers
│   ├── aggregation_helpers.py # Reusable DB aggregation patterns
│   ├── analytics_dashboard_builder.py  # AnalyticsDashboardBuilder
│   ├── analytics_utils.py     # Analytics computations
│   ├── bank_import.py         # Bank statement parsing logic
│   ├── calculations.py        # count_sessions() and financial math
│   ├── calendar_event_processor.py  # CalendarImportProcessor (P-100)
│   ├── calendar_import_helpers.py  # Calendar event → Session import
│   ├── calendar_preflight.py  # Calendar connection preflight checks
│   ├── capacity_helpers.py    # Capacity / utilisation calculations
│   ├── chart_helpers.py       # Chart data preparation
│   ├── client_detail_builder.py  # ClientDetailContextBuilder (P-100)
│   ├── client_helpers.py      # Client convenience helpers
│   ├── contract_form.py       # Contract PDF generation helpers
│   ├── csv_parser.py          # German/US decimal parsing
│   ├── dashboard_context_builder.py  # DashboardContextAssembler (P-100)
│   ├── dashboard_widgets.py   # Dashboard widget data builders
│   ├── date_helpers.py        # DateRangeHelper + working-day counts
│   ├── email_utils.py         # Email composition helpers
│   ├── financial_list_context_builder.py  # FinancialListContextBuilder
│   ├── google_calendar.py     # Google Calendar API wrapper
│   ├── heatmap_utils.py       # Session heatmap generation
│   ├── import_helpers.py      # CSV import base classes
│   ├── invoice_filter_helper.py  # InvoiceFilterHelper
│   ├── invoice_helpers.py     # Invoice number generation
│   ├── practice_analysis.py   # PracticeAnalyzer
│   ├── practice_days.py       # berlin_public_holidays()
│   ├── practice_helpers.py    # Practice-scoped query helpers
│   ├── revenue_helpers.py     # RevenueCalculator
│   ├── tag_helpers.py         # Tag sorting + category helpers
│   ├── tax_context_builder.py # TaxYearContextBuilder (P-100)
│   ├── timeoff_helpers.py     # Time-off query helpers
│   ├── view_helpers.py        # Year/date/search filter helpers
│   └── weekly_focus_widget.py # WeeklyFocus widget logic
│
├── templatetags/
│   ├── payment_tags.py        # Custom template tags/filters (query_string, etc.)
│   ├── dashboard_extras.py    # Dashboard-specific filters
│   └── number_filters.py      # Number formatting filters
│
├── management/
│   └── commands/              # Management commands (see SCRIPTS.md for usage)
│
├── tests/                      # Test suite (~937 tests as of 2026-06-09)
│   └── ...                    # One file per module; see test_*.py files
│
├── static/
│   ├── js/
│   │   ├── charts/            # Modular vanilla-JS chart system (11 modules)
│   │   └── tests/             # JavaScript test suite
│   └── css/
│       ├── tailwind.css       # Single CSS source — all styles live here
│       └── tailwind.out.css   # Compiled output (gitignored; rebuilt by npm run build:css)
└── ...
```

## Views Modules

### 1. `client_views.py` (72 lines)
**Responsibility**: Client management

**Views**:
- `ClientListView`: Client list with sorting
- `ClientIntakeView`: Create new client

**Dependencies**: `Client`, `ClientIntakeForm`

---

### 2. `invoice_views.py` (201 lines)
**Responsibility**: Invoice CRUD operations

**Views**:
- `InvoiceListView`: Invoice list with filters (status, year)
- `InvoiceCreateView`: Create new invoice with line items
- `InvoiceDetailView`: View invoice details

**Features**:
- Automatic invoice number generation
- Formset handling for invoice line items
- Statistics (draft/sent/paid)

**Dependencies**: `Invoice`, `Client`, `InvoiceForm`, `InvoiceItemFormSet`

---

### 3. `dashboard_views.py` (166 lines)
**Responsibility**: Dashboard and home page

**Views**:
- `home()`: Redirect to dashboard
- `dashboard()`: Main dashboard with statistics

**Features**:
- Revenue statistics (total/year/month)
- Monthly revenue trend (12 months)
- Session history heatmap (configurable)
- Status breakdown (draft/sent/paid/cancelled)
- Active clients overview

**Dependencies**: `Invoice`, `Client`, `SessionHistory`, `InvoiceItem`, `heatmap_utils`

---

### 4. `api_views.py` (152 lines)
**Responsibility**: API endpoints and PDF generation

**Views**:
- `next_invoice_number()`: Next invoice number for client
- `invoice_pdf()`: PDF generation (DE/EN)
- `update_invoice_status()`: Status update via POST

**Features**:
- JSON responses for AJAX
- PDF generation with WeasyPrint
- Image optimization (logo/signature)
- Automatic paid_date management

**Dependencies**: `Invoice`, `Client`, `Practice`, `weasyprint`, `PIL`

---

### 5. `analytics_views.py` (128 lines)
**Responsibility**: Analytics and reports

**Views**:
- `analytics_dashboard()`: 5-year analysis (2020–2025)
- `revenue_report()`: Detailed revenue report by payment year

**Features**:
- Revenue trends (monthly, yearly)
- Session type distribution
- Top-10 clients by revenue
- Most active months
- Prior-year revenue comparison

**Dependencies**: `Invoice`, `analytics_utils`

---

### 7. `expense_views.py` (~50 lines) [Uses aggregation_helpers - 23 Dec]
**Responsibility**: Expense management

**Views**:
- `expense_list()`: Expense list with yearly/category overview

**Features**:
- Uses `get_yearly_totals()` from aggregation_helpers
- Uses `get_category_breakdown()` with human-readable names
- Uses `get_grand_total()` with filter conditions
- Tax-deductible vs. non-deductible filtering
- Dark Mode compatible
- Integration with Finance dropdown menu

**Dependencies**: `CompanyExpense`, `utils.aggregation_helpers`

---

### 8. `withdrawal_views.py` (~65 lines) [Uses aggregation_helpers - 23 Dec]
**Responsibility**: Withdrawal management

**Views**:
- `withdrawal_list()`: Withdrawal list with monthly overview
- `withdrawal_create()`: Create new withdrawal
- `withdrawal_update()`: Update withdrawal
- `withdrawal_delete()`: Delete withdrawal

**Features**:
- Uses `get_yearly_totals()` from aggregation_helpers
- Uses `get_monthly_breakdown()` for current year
- Uses `get_grand_total()` for total calculations
- CRUD operations with German UI messages
- Category filtering
- Integration with analytics dashboard
- Dark mode compatible

**Dependencies**: `CompanyWithdrawal`, `utils.aggregation_helpers`, `CompanyWithdrawalForm`

---

### 9. `tax_views.py` (~130 lines) [Uses aggregation_helpers - 23 Dec]
**Responsibility**: Tax year overview

**Views**:
- `tax_year_summary()`: Comprehensive tax year report

**Features**:
- Revenue breakdown (paid invoices with paid_date accuracy)
- Expense breakdown by category using `get_category_breakdown()`
- Withdrawal breakdown by category using `get_category_breakdown()`
- Uses `get_grand_total()` for expense/withdrawal totals
- Profit calculations (Gross: Revenue - Expenses, Net: Gross - Withdrawals)
- Year filter with `get_year_from_request()`
- Tax deductible expense filtering

**Dependencies**: `Invoice`, `CompanyExpense`, `CompanyWithdrawal`, `utils.aggregation_helpers`, `utils.revenue_helpers`

---

## Utils Modules

### 1. `calculations.py` (48 lines)
**Responsibility**: Session counting & financial calculations

**Functions**:
- `count_sessions()`: Accurate session counting with duration normalization
  - Formula: `(duration / 60.0) * quantity`
  - Returns float for precision
- `count_sessions_rounded()`: Rounded session counts (integer)
- `apply_remainder_distribution()`: Remainder distribution for exact totals
  - **Problem**: 340€ ÷ 3 = 113.33€ × 3 = 339.99€ (0.01€ lost)
  - **Solution**: Last item gets the remainder (113.33€ + 113.33€ + 113.34€ = 340€)

**Usage**: Heatmap, analytics, reconciliation, import views

---

### 2. `csv_parser.py` (32 lines)
**Responsibility**: Decimal parsing

**Functions**:
- `parse_german_decimal()`: **Enhanced** — Intelligent format detection
  - Handles German format: `1.234,56` (dot=thousand, comma=decimal)
  - Handles US format: `1,234.56` (comma=thousand, dot=decimal)
  - Handles mixed format: `-2,160.00 €` (auto-detects last separator as decimal)
  - Logic: If both separators present, last one is decimal separator

**Usage**: Import views (invoices, withdrawals, expenses)

---

### 3. `reconciliation.py` (289 lines)
**Responsibility**: Session history vs invoice items reconciliation

**Functions**:
- `group_items_by_month()`: Group invoice items by month
- `count_sessions_in_items()`: Count sessions using centralized logic
- `build_invoice_summary()`: Build monthly invoice summaries
- `detect_discrepancies()`: Detect SessionHistory/InvoiceItem mismatches
- `build_reconciliation_data()`: Main orchestration function

**Usage**: reconciliation_views.py, management commands

---

### 4. `date_helpers.py` (87 lines)
**Responsibility**: Date range operations

**Class**: `DateRangeHelper`
- `get_month_range()`: First and last day of month
- `get_year_range()`: First and last day of year
- `get_previous_month()`: Previous month date
- `get_next_month()`: Next month date

**Usage**: Analytics, heatmap, reports

---

### 5. `invoice_helpers.py` (53 lines)
**Responsibility**: Invoice numbering logic

**Functions**:
- `get_next_invoice_number()`: Generate next invoice number for client
  - Handles sequential numbering
  - Handles gaps in sequence
  - Handles malformed numbers

**Tests**: 10 comprehensive tests

**Usage**: InvoiceCreateView, InvoiceDetailView, API endpoints

---

### 6. `revenue_helpers.py` (143 lines)
**Responsibility**: Revenue aggregation and calculations

**Class**: `RevenueCalculator`
- `get_paid_invoices()`: Get paid invoices with optional year filter
- `get_total_revenue()`: Total revenue from paid invoices
- `get_year_revenue()`: Revenue for specific year (paid_date aware)
- `get_status_breakdown()`: Invoice counts/totals by status (single query)

**Usage**: Dashboard, tax views, invoice list views

---

### 7. `view_helpers.py` (167 lines)
**Responsibility**: Reusable view helper functions

**Functions**:
- `get_date_range_from_request()`: Parse start/end date from request
- `filter_queryset_by_date_range()`: Apply date filters to queryset
- `get_year_from_request()`: Parse and validate year parameter
- `paginate_queryset()`: Generic pagination helper
- `get_search_query_filter()`: Build Q object for multi-field search

**Tests**: 10 tests

**Usage**: All views with date filters, year filters, search

---

**Responsibility**: Reusable view mixins for ListView patterns

**Mixins**:
- `YearFilterMixin`: Automatic year filtering with context
  - Attributes: `date_field`, `year_param`
  - Adds: `current_year`, `available_years` to context
- `StatusFilterMixin`: Status filtering for list views
  - Attributes: `status_field`, `status_param`, `valid_statuses`
  - Adds: `current_status` to context
- `SearchMixin`: Multi-field search capability
  - Attributes: `search_param`, `search_fields`
  - Adds: `search_query` to context
- `CombinedFilterMixin`: Combines all three mixins

**Usage Example**:
```python
class ExpenseListView(YearFilterMixin, ListView):
    model = CompanyExpense
    date_field = 'date'
    template_name = 'expense_list.html'
```

**Usage**: Future ListView refactorings

---

### 9. `aggregation_helpers.py` (200 lines) [NEW - 23 Dec 2025]
**Responsibility**: Reusable aggregation patterns for data analysis

**Functions**:
- `get_yearly_totals()`: Aggregate by year with totals
  - Params: queryset, date_field, amount_field, order
  - Returns: List of {year, total}
- `get_category_breakdown()`: Aggregate by category with counts
  - Params: queryset, category_field, amount_field, category_choices
  - Returns: List of {category, category_name, total, count}
- `get_monthly_breakdown()`: Aggregate by month for specific year
  - Params: queryset, year, date_field, amount_field
  - Returns: Dict {YYYY-MM: Decimal}
- `get_grand_total()`: Calculate total with optional filtering
  - Params: queryset, amount_field, filter_condition
  - Returns: Decimal
- `get_year_over_year_comparison()`: Compare totals across years
  - Params: queryset, years, date_field, amount_field
  - Returns: Dict with totals and growth percentages

**Tests**: 10 comprehensive tests in test_aggregation_helpers.py

**Usage**: expense_views.py, withdrawal_views.py, tax_views.py

---

## Import Compatibility

The `views/__init__.py` exports all views so that URLs remain **unchanged**:

```python
# urls.py
from .views import (
    ClientListView,
    InvoiceCreateView,
    analytics_dashboard,
    import_invoices,
    # ... all other views
)
```

No changes to `urls.py`, `admin.py`, or templates required!

---

## Benefits of the New Structure

### 1. **Maintainability**
- Each file < 800 lines (average 200 lines)
- Clear responsibilities (Single Responsibility Principle)
- Easier navigation and debugging

### 2. **Reusability**
- Utils can be used in management commands, tests, and tasks
- CSV parser is independent of views
- Validators can be used in forms/serializers

### 3. **Testability**
- Isolated functions are easier to test
- Utils have no Django view dependencies
- Mocking is simpler

### 4. **Scalability**
- New features can be added in new files
- Import logic can be split further (e.g. invoice_import.py, session_import.py)
- Utils can be extended without touching views

### 5. **Code deduplication**
- `apply_remainder_distribution()` instead of copy-paste
- `parse_german_decimal()` centrally available
- `validate_paid_date()` reusable

---

## Migration history (summary)

| Date | Change |
|------|--------|
| 2025-12-16 | Initial refactor: monolithic `views.py` (1 480 lines) → 7 view modules + utils |
| 2025-12-18 | Expense tracking added; import views packaged; aggregation helpers extracted |
| 2025-12-21 | Performance: N+1 fixes, DB indexes (migrations 0013–0014), `select_related` everywhere |
| 2025-12-23 | Template components (`pagination.html`, `empty_state.html`); CSS filter-bar components |
| 2025-12-26 | Models package (9 → now 17 modules); chart system modularised (11 JS modules) |
| Jan 2026 | CRUD mixin refactoring (`PracticeScopedCreateView/UpdateView/DeleteView/ListView`) |
| Feb–Apr 2026 | P-031–P-042: inquiries, calendar, clinical docs, analytics, batch invoicing, tax allocation; codebase renamed `payments_app` → `my_practice` (P-032) |

For full detail see [docs/CHANGELOG.md](../CHANGELOG.md).

---

## Support

For questions about code structure or extensions:
1. Identify the relevant module from the directory tree above
2. Check docstrings in the module
3. For performance patterns: see [PERFORMANCE.md](PERFORMANCE.md)
4. For available utility classes: see [CLAUDE.md](../../CLAUDE.md) "Available Utility Classes" section

