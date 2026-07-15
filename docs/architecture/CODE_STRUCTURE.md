# my_practice — Code Structure

**Last updated: 2026-07-15**

## Overview

The application was refactored from a monolithic `views.py` into a modular structure with clear separation of concerns. This document describes the current layout; see [docs/CHANGELOG.md](../CHANGELOG.md) for the evolution history.

## Directory Structure

```
app/my_practice/
├── models/                     # Domain models package (17 modules)
│   ├── __init__.py            # Package exports with __all__
│   ├── base.py                # TimestampedModel base class, PracticeScopedManager
│   ├── bank_statement.py      # BankTransaction
│   ├── calendar.py            # GoogleCalendarToken, PendingCalendarEvent
│   ├── client.py              # Client management
│   ├── client_alias.py        # ClientAlias / search name
│   ├── clinical.py            # ClientProfile, SessionLog, SupervisionItem, ClientNote
│   ├── financial.py           # CompanyWithdrawal, CompanyExpense
│   ├── gebueh.py              # GebuhZiffer, Leistungserfassung (P-046)
│   ├── inquiry.py             # ClientInquiry lead tracking
│   ├── invoice.py             # Invoice, InvoiceItem
│   ├── operational.py         # OperationalChecklist + items
│   ├── practice.py            # Practice, UserPractice, CapacityPeriod
│   ├── service.py             # ServiceType
│   ├── session.py             # Session
│   ├── tag.py                 # ClientTag, ClientTagAssignment
│   ├── timeoff.py             # TimeOff tracking
│   └── todo.py                # PracticeTodo
│
├── views/                      # View modules
│   ├── __init__.py            # Central exports for all views
│   ├── crud_mixins.py         # PracticeScopedCreate/Update/Delete/ListView, InvoiceFormsetMixin
│   ├── analytics_views.py     # Analytics & revenue reports
│   ├── api_views.py           # JSON API endpoints, PDF generation, invoice_batch_download
│   ├── bank_import_views.py   # Bank statement CSV import & review
│   ├── calendar_views.py      # Google Calendar OAuth + session import approval
│   ├── client_views.py        # Client list, detail, intake
│   ├── clinical_views.py      # SessionLog, ClientNote, SupervisionItem, triage
│   ├── dashboard_views.py     # Dashboard (delegates to DashboardContextAssembler)
│   ├── email_views.py         # Email compose + send (invoice, reminder, contract, …)
│   ├── expense_views.py       # Expense CRUD + list
│   ├── inquiry_views.py       # Lead tracking + funnel analytics
│   ├── invoice_views.py       # Invoice CRUD + billing overview + monthly batch billing
│   ├── operational_views.py   # Operational checklist
│   ├── practice_views.py      # Practice settings + multi-practice management
│   ├── search_views.py        # Global search
│   ├── tag_views.py           # Client tag management
│   ├── tax_views.py           # Tax year summary, quarterly overview, workday audit
│   ├── todo_views.py          # Practice todo list
│   └── withdrawal_views.py    # Withdrawal CRUD + list
│
├── utils/                      # Utility functions (39 modules)
│   ├── __init__.py            # Central exports
│   ├── action_queue_builder.py     # ActionQueueBuilder (dashboard action queue)
│   ├── agenda_helpers.py           # AgendaWidgetBuilder (daily/weekly agenda)
│   ├── aggregation_helpers.py      # Reusable DB aggregation patterns
│   ├── analytics_dashboard_builder.py  # AnalyticsDashboardBuilder
│   ├── analytics_utils.py          # Analytics computations
│   ├── bank_import.py              # Bank statement CSV parsing
│   ├── billing_helpers.py          # Session→InvoiceItem: build_service_type_map,
│   │                               #   resolve_session_rate, is_session_already_billed,
│   │                               #   create_invoice_item_for_session
│   ├── calculations.py             # count_sessions(), financial math
│   ├── calendar_event_processor.py # CalendarImportProcessor
│   ├── calendar_import_helpers.py  # Calendar event → Session import helpers
│   ├── calendar_preflight.py       # Calendar connection preflight checks
│   ├── capacity_helpers.py         # Capacity / utilisation calculations
│   ├── chart_helpers.py            # Chart data preparation
│   ├── client_detail_builder.py    # ClientDetailContextBuilder
│   ├── client_helpers.py           # Client convenience helpers
│   ├── contract_form.py            # Contract PDF generation helpers
│   ├── csv_parser.py               # German/US decimal parsing
│   ├── dashboard_context_builder.py # DashboardContextAssembler
│   ├── dashboard_widgets.py        # Dashboard widget data builders (9 builders)
│   ├── date_helpers.py             # DateRangeHelper, working-day counts,
│   │                               #   get_quarter_range, get_quarter_for_date
│   ├── email_utils.py              # Email composition helpers
│   ├── file_processing.py          # Uploaded media compression (images, PDFs)
│   ├── financial_list_context_builder.py  # FinancialListContextBuilder
│   ├── gebueh_helpers.py           # GebüH block building shared by PDF + invoice detail
│   ├── google_calendar.py          # Google Calendar API wrapper
│   ├── heatmap_utils.py            # Session heatmap generation
│   ├── import_helpers.py           # CSV import base classes
│   ├── invoice_filter_helper.py    # InvoiceFilterHelper
│   ├── invoice_helpers.py          # get_next_invoice_number()
│   ├── practice_analysis.py        # PracticeAnalyzer
│   ├── practice_days.py            # berlin_public_holidays(), PracticeDayCalculator,
│   │                               #   WorkdayAuditCalculator
│   ├── practice_helpers.py         # Practice-scoped query helpers
│   ├── questionnaire_content.py    # Loader for clinical questionnaire content (P-118/119/120)
│   ├── revenue_helpers.py          # RevenueCalculator
│   ├── tag_helpers.py              # Tag sorting + category helpers
│   ├── tax_context_builder.py      # TaxYearContextBuilder, available_data_years()
│   ├── timeoff_helpers.py          # Time-off query helpers
│   ├── view_helpers.py             # Year/date/search filter helpers
│   └── weekly_focus_widget.py      # WeeklyFocusWidgetBuilder
│
├── templatetags/
│   ├── payment_tags.py        # Custom template tags/filters (query_string, etc.)
│   ├── dashboard_extras.py    # Dashboard-specific filters
│   └── number_filters.py      # Number formatting filters
│
├── management/
│   └── commands/              # Management commands (see docs/operations/SCRIPTS.md)
│
├── tests/                      # Test suite (~1340+ tests)
│   └── ...                    # One file per module; see test_*.py files
│
├── static/
│   ├── js/
│   │   ├── charts/            # Modular vanilla-JS chart system (11 modules)
│   │   └── tests/             # JavaScript test suite
│   └── css/
│       ├── tailwind.css       # Single CSS source — all styles live here
│       └── tailwind.out.css   # Compiled output (gitignored)
└── ...
```

## Key Architectural Patterns

### Builder classes for complex context

Views with more than trivial context preparation delegate to builder classes:

```python
# Dashboard
from my_practice.utils import DashboardContextAssembler
context = DashboardContextAssembler(request).build()

# Tax year summary
from my_practice.utils import TaxYearContextBuilder
context = TaxYearContextBuilder(year, practice, user).build(expense_sort="date")

# Analytics
from my_practice.utils import AnalyticsDashboardBuilder
context = AnalyticsDashboardBuilder(start_date, end_date).build_context()
```

### Dashboard architecture (as of v0.2.7 P-117 redesign)

`dashboard_views.py` is a thin dispatcher (22 lines). All data preparation lives in:
- `DashboardContextAssembler` (`dashboard_context_builder.py`) — orchestrates widget builders
- Eleven widget builders: eight in `dashboard_widgets.py` (`InvoiceActionsWidgetBuilder`, `ClientAttentionWidgetBuilder`, `SessionImportWidgetBuilder`, `PendingCalendarWidgetBuilder`, `ChecklistWidgetBuilder`, `CapacityMonitoringWidgetBuilder`, `TaxQuarterWidgetBuilder`, `BankImportReminderWidgetBuilder`), plus `AgendaWidgetBuilder` (`agenda_helpers.py`), `WeeklyFocusWidgetBuilder` (`weekly_focus_widget.py`), and `ActionQueueBuilder` (`action_queue_builder.py`)

### Session billing helpers (`utils/billing_helpers.py`)

Three call sites (add-to-invoice, create-invoice-with-sessions, calendar approval) share:
- `build_service_type_map(practice)` — `{duration: ServiceType}` dict for the practice
- `resolve_session_rate(client, service_type)` — handles `therapy_free` zero-rating
- `is_session_already_billed(session)` — excludes cancelled invoices
- `create_invoice_item_for_session(invoice, session, map, fallback)` — full helper with all guards

### CRUD mixins (`views/crud_mixins.py`)

```python
class ExpenseCreateView(PracticeScopedCreateView):
    model = CompanyExpense
    form_class = CompanyExpenseForm
    success_url = reverse_lazy("expense_list")
    success_message = "Ausgabe vom {obj.date:%d.%m.%Y} erfolgreich erstellt."
```

`PracticeScopedUpdateView`, `PracticeScopedDeleteView`, `PracticeScopedListView` follow the same pattern.
`NextRedirectMixin` adds `?next=` redirect support (mix in before the `PracticeScoped*` base) —
`get_success_url()` honors `?next=`, falling back to `success_url`, and exposes the raw value to
templates as `context["next"]`. `InvoiceFormsetMixin` handles inline `InvoiceItemFormSet` context.

### Centralized calculations

| Helper | Location | Use for |
|--------|----------|---------|
| `RevenueCalculator` | `revenue_helpers.py` | All revenue queries — always use this, never filter manually |
| `DateRangeHelper` | `date_helpers.py` | Month/quarter/year ranges, working-day counts |
| `available_data_years(practice)` | `tax_context_builder.py` | Year-selector dropdowns in tax views |
| `count_sessions(items)` | `calculations.py` | Session count with duration normalization |
| `get_next_invoice_number(client)` | `invoice_helpers.py` | Invoice number generation |
| `build_client_map()` | `import_helpers.py` | Optimized code→client mapping |

### Capacity periods (v0.2.9)

Weekly capacity is no longer hard-coded at 2023-08-01. The `CapacityPeriod` model holds one row per change, editable in Practice Settings. `capacity_helpers.get_weekly_capacity_for_date(date)` returns the correct hours per week for any date. All utilisation calculations in `analytics_utils.py` and `practice_days.py` consume it.

## Views Quick Reference

| Module | Responsibility | Notable patterns |
|--------|---------------|-----------------|
| `dashboard_views.py` | Dashboard home | Pure dispatcher; delegates to `DashboardContextAssembler` |
| `invoice_views.py` | Invoice CRUD + billing overview | `InvoiceFormsetMixin`; `billing_helpers` for session items |
| `client_views.py` | Client list + intake | `PracticeScopedListView` |
| `clinical_views.py` | SessionLog, Notes, Supervision, triage | Fernet encryption for notes/sessions |
| `calendar_views.py` | Google Calendar OAuth + event approval | `CalendarImportProcessor`; `resolve_session_rate` |
| `email_views.py` | Email compose + send | `BaseClientEmailView` base class; 5 concrete views |
| `bank_import_views.py` | CSV import + manual review | `_fetch_invoice_maps()` batch helper; stored `total` |
| `tax_views.py` | Tax summary, quarters, workday audit | `TaxYearContextBuilder`; `available_data_years()` |
| `analytics_views.py` | Revenue & session analytics | `AnalyticsDashboardBuilder` |
| `inquiry_views.py` | Lead pipeline | Funnel analytics, email templates, client code suggester |

## Support

For questions about code structure or extensions:
1. Identify the relevant module from the directory tree above
2. Check docstrings in the module
3. For performance patterns: see [PERFORMANCE.md](PERFORMANCE.md)
4. For available utility classes: see [CLAUDE.md](../../CLAUDE.md) "Available Utility Classes" section
