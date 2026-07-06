"""
Utility functions for the payments app.
"""

from .agenda_helpers import AgendaItem, AgendaWidgetBuilder
from .analytics_dashboard_builder import AnalyticsDashboardBuilder
from .action_queue_builder import ActionQueueBuilder
from .client_detail_builder import ClientDetailContextBuilder
from .dashboard_context_builder import DashboardContextAssembler
from .tax_context_builder import TaxYearContextBuilder
from .bank_import import BankStatementImporter
from .calculations import (
    apply_remainder_distribution,
    count_session_hours,
    count_sessions,
    count_sessions_rounded,
)
from .chart_helpers import (
    GERMAN_MONTHS_SHORT,
    aggregate_invoice_items_by_month,
    format_month_key,
    format_month_label,
    prepare_monthly_chart_data,
)
from .client_helpers import (
    annotate_activity_status,
    calculate_client_session_stats,
    flatten_invoice_items,
    group_clients_by_activity,
    group_clients_by_year,
)
from .dashboard_widgets import (
    BankImportReminderWidgetBuilder,
    CapacityMonitoringWidgetBuilder,
    ChecklistWidgetBuilder,
    ClientAttentionWidgetBuilder,
    InvoiceActionsWidgetBuilder,
    PendingCalendarWidgetBuilder,
    SessionImportWidgetBuilder,
    TaxQuarterWidgetBuilder,
)
from .date_helpers import DateRangeHelper
from .financial_list_context_builder import FinancialListContextBuilder
from .import_helpers import build_client_map
from .invoice_filter_helper import InvoiceFilterHelper
from .billing_helpers import (
    build_service_type_map,
    create_invoice_item_for_session,
    is_session_already_billed,
    resolve_session_rate,
)
from .invoice_helpers import get_next_invoice_number
from .practice_days import FahrtkostenResult, PracticeDayCalculator
from .practice_helpers import (
    get_current_practice,
    get_user_practices,
    is_practice_owner,
    require_practice,
    switch_practice,
)
from .revenue_helpers import RevenueCalculator
from .tag_helpers import (
    SESSION_LOG_MIN_DURATION,
    SESSION_LOG_WINDOW_DAYS,
    remove_no_next_session_tag,
    sort_tags_by_category,
)
from .weekly_focus_widget import WeeklyFocusWidgetBuilder

__all__ = [
    "count_sessions",
    "count_session_hours",
    "count_sessions_rounded",
    "apply_remainder_distribution",
    "get_next_invoice_number",
    "build_service_type_map",
    "create_invoice_item_for_session",
    "is_session_already_billed",
    "resolve_session_rate",
    "RevenueCalculator",
    "DateRangeHelper",
    "format_month_key",
    "format_month_label",
    "aggregate_invoice_items_by_month",
    "GERMAN_MONTHS_SHORT",
    "prepare_monthly_chart_data",
    "annotate_activity_status",
    "flatten_invoice_items",
    "calculate_client_session_stats",
    "group_clients_by_activity",
    "group_clients_by_year",
    "sort_tags_by_category",
    "remove_no_next_session_tag",
    "SESSION_LOG_WINDOW_DAYS",
    "SESSION_LOG_MIN_DURATION",
    "build_client_map",
    "BankStatementImporter",
    "AnalyticsDashboardBuilder",
    "ActionQueueBuilder",
    "ClientDetailContextBuilder",
    "DashboardContextAssembler",
    "TaxYearContextBuilder",
    "FinancialListContextBuilder",
    "InvoiceFilterHelper",
    "AgendaWidgetBuilder",
    "AgendaItem",
    "SessionImportWidgetBuilder",
    "ClientAttentionWidgetBuilder",
    "InvoiceActionsWidgetBuilder",
    "BankImportReminderWidgetBuilder",
    "ChecklistWidgetBuilder",
    "CapacityMonitoringWidgetBuilder",
    "PendingCalendarWidgetBuilder",
    "TaxQuarterWidgetBuilder",
    "get_current_practice",
    "require_practice",
    "switch_practice",
    "get_user_practices",
    "is_practice_owner",
    "PracticeDayCalculator",
    "FahrtkostenResult",
    "WeeklyFocusWidgetBuilder",
]
