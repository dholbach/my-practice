"""
Views package - all views are imported here for compatibility with URLs.
"""

# Analytics views
from .analytics_views import (
    analytics_dashboard,
    practice_analysis_redirect,
    revenue_report,
)

# API views
from .api_views import (
    contract_pdf,
    intake_form_pdf,
    invoice_batch_download,
    invoice_pdf,
    next_invoice_number,
    questionnaire_pdf,
    update_invoice_status,
)

# Bank import views
from .bank_import_views import (
    BankExpenseReviewView,
    BankImportView,
    BankReviewView,
    BankWithdrawalReviewView,
    bank_transaction_detail,
)

# Calendar import views
from .calendar_views import (
    calendar_approval_queue,
    calendar_authorize,
    calendar_event_quick_action,
    calendar_import,
    calendar_import_events,
    calendar_oauth2callback,
    calendar_queue_import,
    calendar_queue_skip,
    calendar_queue_skip_duplicates,
)

# Client views
from .client_views import (
    ClientIntakeView,
    ClientListView,
    client_detail,
    client_document_delete,
    client_document_upload,
    client_gdpr_delete,
    client_gdpr_delete_confirm,
    client_onboarding_step,
    suggest_client_code,
)

# Clinical documentation views (P-009)
from .clinical_views import (
    client_note_create,
    client_note_delete,
    client_note_update,
    client_profile_save,
    client_triage_summary,
    gebueh_leistung_create,
    session_bill,
    session_delete,
    session_log_create,
    session_log_delete,
    session_duration_edit,
    session_log_edit,
    session_log_mark_noshow,
    session_toggle_billable,
    supervision_item_create,
    supervision_item_delete,
    supervision_item_toggle,
    supervision_queue,
)

# Dashboard views
from .dashboard_views import dashboard, home

# Email views
from .email_views import (
    SendCancellationEmailView,
    SendContractEmailView,
    SendIntakeFormEmailView,
    SendInvoiceEmailView,
    SendPaymentReminderView,
    SendQuestionnaireEmailView,
    SendQuestionnairePdfEmailView,
)

# Expense views
from .expense_views import (
    ExpenseCreateView,
    ExpenseDeleteView,
    ExpenseUpdateView,
    expense_link_transaction,
    expense_list,
    expense_merge,
    expense_receipt_delete,
    expense_unlink_transaction,
)

# Invoice views
from .invoice_views import (
    InvoiceCreateView,
    InvoiceDetailView,
    InvoiceEditView,
    InvoiceListView,
    add_sessions_to_invoice,
    billing_open_overview,
    create_invoice_with_sessions,
    invoice_delete,
    monthly_billing_overview,
    monthly_billing_redirect,
)

# Operational checklist views
from .operational_views import (
    OperationalChecklistView,
    boilerplate_view,
    checklist_complete,
    checklist_pause_item,
    checklist_unpause_item,
)

# Practice views
from .practice_views import (
    PracticeCreateView,
    PracticeDeleteView,
    PracticeManagementView,
    PracticeUpdateView,
    practice_select,
    practice_switch,
)

# Search views
from .search_views import global_search

# Tag views
from .tag_views import (
    TagCreateView,
    TagDeleteView,
    TagListView,
    TagUpdateView,
    client_add_tag,
    client_remove_tag,
    get_available_tags,
)

# Tax views
from .tax_views import save_tax_year_note, tax_quarter_overview, tax_workday_audit, tax_year_summary

# TODO views
from .todo_views import (
    TodoCreateView,
    TodoDeleteView,
    TodoListView,
    TodoUpdateView,
    todo_toggle_complete,
    todo_toggle_focus,
)

# Time-off views
from .timeoff_views import (
    SendTimeOffNoticeView,
    TimeOffCreateView,
    TimeOffDeleteView,
    TimeOffUpdateView,
    timeoff_list,
)

# Withdrawal views
from .withdrawal_views import (
    WithdrawalCreateView,
    WithdrawalDeleteView,
    WithdrawalUpdateView,
    withdrawal_list,
)

# Inquiry views (P-031)
from .inquiry_views import (  # noqa: F401
    InquiryListView,
    InquiryCreateView,
    InquiryUpdateView,
    InquiryDeleteView,
    InquiryConvertView,
    MarketingPeriodCreateView,
    MarketingPeriodUpdateView,
    MarketingPeriodDeleteView,
)

__all__ = [
    # Client views
    "ClientListView",
    "ClientIntakeView",
    "client_detail",
    "client_document_upload",
    "client_document_delete",
    "client_gdpr_delete_confirm",
    "client_gdpr_delete",
    "client_onboarding_step",
    "suggest_client_code",
    # Invoice views
    "InvoiceListView",
    "InvoiceCreateView",
    "InvoiceDetailView",
    "InvoiceEditView",
    "add_sessions_to_invoice",
    "billing_open_overview",
    "create_invoice_with_sessions",
    "invoice_delete",
    "monthly_billing_overview",
    "monthly_billing_redirect",
    # Dashboard views
    "home",
    "dashboard",
    # Practice views
    "practice_switch",
    "practice_select",
    "PracticeManagementView",
    "PracticeCreateView",
    "PracticeUpdateView",
    "PracticeDeleteView",
    # TODO views
    "TodoListView",
    "TodoCreateView",
    "TodoUpdateView",
    "TodoDeleteView",
    "todo_toggle_complete",
    "todo_toggle_focus",
    # API views
    "contract_pdf",
    "intake_form_pdf",
    "invoice_batch_download",
    "next_invoice_number",
    "invoice_pdf",
    "questionnaire_pdf",
    "update_invoice_status",
    # Bank import views
    "BankExpenseReviewView",
    "BankImportView",
    "BankReviewView",
    "BankWithdrawalReviewView",
    "bank_transaction_detail",
    # Email views
    "SendCancellationEmailView",
    "SendContractEmailView",
    "SendIntakeFormEmailView",
    "SendInvoiceEmailView",
    "SendPaymentReminderView",
    "SendQuestionnaireEmailView",
    "SendQuestionnairePdfEmailView",
    # Time-off views
    "timeoff_list",
    "TimeOffCreateView",
    "TimeOffUpdateView",
    "TimeOffDeleteView",
    "SendTimeOffNoticeView",
    # Withdrawal views
    "withdrawal_list",
    "WithdrawalCreateView",
    "WithdrawalUpdateView",
    "WithdrawalDeleteView",
    # Expense views
    "expense_list",
    "ExpenseCreateView",
    "ExpenseUpdateView",
    "ExpenseDeleteView",
    "expense_receipt_delete",
    "expense_link_transaction",
    "expense_unlink_transaction",
    "expense_merge",
    # Analytics views
    "analytics_dashboard",
    "revenue_report",
    "practice_analysis_redirect",
    # Tax views
    "tax_year_summary",
    "tax_quarter_overview",
    "save_tax_year_note",
    "tax_workday_audit",
    # Tag views
    "TagListView",
    "TagCreateView",
    "TagUpdateView",
    "TagDeleteView",
    "client_add_tag",
    "client_remove_tag",
    "get_available_tags",
    # Calendar views
    "calendar_authorize",
    "calendar_oauth2callback",
    "calendar_import",
    "calendar_import_events",
    "calendar_approval_queue",
    "calendar_queue_import",
    "calendar_queue_skip",
    "calendar_queue_skip_duplicates",
    "calendar_event_quick_action",
    # Search views
    "global_search",
    # Operational checklist views
    "OperationalChecklistView",
    "boilerplate_view",
    "checklist_complete",
    "checklist_pause_item",
    "checklist_unpause_item",
    # Clinical documentation views (P-009)
    "client_note_create",
    "client_note_delete",
    "client_note_update",
    "client_profile_save",
    "client_triage_summary",
    "gebueh_leistung_create",
    "session_bill",
    "session_delete",
    "session_log_create",
    "session_log_delete",
    "session_duration_edit",
    "session_log_edit",
    "session_log_mark_noshow",
    "session_toggle_billable",
    "supervision_item_create",
    "supervision_item_delete",
    "supervision_item_toggle",
    "supervision_queue",
]
