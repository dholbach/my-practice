"""
URL configuration for payments app.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    # Practice management URLs
    path("practice/switch/<slug:slug>/", views.practice_switch, name="practice_switch"),
    path("practice/select/", views.practice_select, name="practice_select"),
    path(
        "practice/manage/",
        views.PracticeManagementView.as_view(),
        name="practice_management",
    ),
    path("practice/create/", views.PracticeCreateView.as_view(), name="practice_create"),
    path(
        "practice/<slug:slug>/edit/",
        views.PracticeUpdateView.as_view(),
        name="practice_edit",
    ),
    path(
        "practice/<slug:slug>/delete/",
        views.PracticeDeleteView.as_view(),
        name="practice_delete",
    ),
    path("clients/", views.ClientListView.as_view(), name="client_list"),
    path("clients/new/", views.ClientIntakeView.as_view(), name="client_intake"),
    path("clients/<int:pk>/detail/", views.client_detail, name="client_detail"),
    path("clients/<int:pk>/edit/", views.ClientIntakeView.as_view(), name="client_edit"),
    # Inquiry / lead tracking (P-031)
    path("inquiries/", views.InquiryListView.as_view(), name="inquiry_list"),
    path("inquiries/new/", views.InquiryCreateView.as_view(), name="inquiry_create"),
    path("inquiries/<int:pk>/edit/", views.InquiryUpdateView.as_view(), name="inquiry_edit"),
    path("inquiries/<int:pk>/delete/", views.InquiryDeleteView.as_view(), name="inquiry_delete"),
    path("inquiries/<int:pk>/convert/", views.InquiryConvertView.as_view(), name="inquiry_convert"),
    path(
        "marketing-periods/new/",
        views.MarketingPeriodCreateView.as_view(),
        name="marketing_period_create",
    ),
    path(
        "marketing-periods/<int:pk>/edit/",
        views.MarketingPeriodUpdateView.as_view(),
        name="marketing_period_edit",
    ),
    path(
        "marketing-periods/<int:pk>/delete/",
        views.MarketingPeriodDeleteView.as_view(),
        name="marketing_period_delete",
    ),
    path("invoices/", views.InvoiceListView.as_view(), name="invoice_list"),
    path("billing/", views.monthly_billing_redirect, name="monthly_billing"),
    path("billing/open/", views.billing_open_overview, name="billing_open_overview"),
    path("billing/<str:month>/", views.monthly_billing_overview, name="monthly_billing_overview"),
    path("invoices/new/", views.InvoiceCreateView.as_view(), name="invoice_create"),
    path("invoices/next-number/", views.next_invoice_number, name="next_invoice_number"),
    path(
        "invoices/download/",
        views.invoice_batch_download,
        name="invoice_batch_download",
    ),
    path("invoices/<int:pk>/", views.InvoiceDetailView.as_view(), name="invoice_detail"),
    path("invoices/<int:pk>/edit/", views.InvoiceEditView.as_view(), name="invoice_edit"),
    path(
        "invoices/<int:pk>/add-sessions/",
        views.add_sessions_to_invoice,
        name="invoice_add_sessions",
    ),
    path(
        "invoices/create-with-sessions/",
        views.create_invoice_with_sessions,
        name="invoice_create_with_sessions",
    ),
    path("invoices/<int:pk>/delete/", views.invoice_delete, name="invoice_delete"),
    path("invoices/<int:pk>/pdf/", views.invoice_pdf, name="invoice_pdf"),
    path("clients/<int:pk>/contract-pdf/", views.contract_pdf, name="contract_pdf"),
    path(
        "clients/<int:pk>/send-contract/",
        views.SendContractEmailView.as_view(),
        name="send_contract_email",
    ),
    path("clients/<int:pk>/intake-form-pdf/", views.intake_form_pdf, name="intake_form_pdf"),
    path(
        "clients/<int:pk>/send-questionnaire/",
        views.SendQuestionnaireEmailView.as_view(),
        name="send_questionnaire_docx",
    ),
    path(
        "clients/<int:pk>/onboarding/", views.client_onboarding_step, name="client_onboarding_step"
    ),
    path(
        "clients/<int:pk>/documents/upload/",
        views.client_document_upload,
        name="client_document_upload",
    ),
    path(
        "documents/<int:pk>/delete/",
        views.client_document_delete,
        name="client_document_delete",
    ),
    path(
        "clients/<int:pk>/gdpr-delete/",
        views.client_gdpr_delete_confirm,
        name="client_gdpr_delete_confirm",
    ),
    path(
        "clients/<int:pk>/gdpr-delete/confirm/",
        views.client_gdpr_delete,
        name="client_gdpr_delete",
    ),
    path(
        "invoices/<int:invoice_id>/send-email/",
        views.SendInvoiceEmailView.as_view(),
        name="send_invoice_email",
    ),
    path(
        "clients/<int:pk>/payment-reminder/",
        views.SendPaymentReminderView.as_view(),
        name="send_payment_reminder",
    ),
    path(
        "clients/<int:pk>/cancellation-email/",
        views.SendCancellationEmailView.as_view(),
        name="send_cancellation_email",
    ),
    path(
        "invoices/<int:pk>/status/",
        views.update_invoice_status,
        name="update_invoice_status",
    ),
    path("withdrawals/", views.withdrawal_list, name="withdrawal_list"),
    path(
        "withdrawals/new/",
        views.WithdrawalCreateView.as_view(),
        name="withdrawal_create",
    ),
    path(
        "withdrawals/<int:pk>/edit/",
        views.WithdrawalUpdateView.as_view(),
        name="withdrawal_update",
    ),
    path(
        "withdrawals/<int:pk>/delete/",
        views.WithdrawalDeleteView.as_view(),
        name="withdrawal_delete",
    ),
    path("expenses/", views.expense_list, name="expense_list"),
    path("expenses/new/", views.ExpenseCreateView.as_view(), name="expense_create"),
    path(
        "expenses/<int:pk>/edit/",
        views.ExpenseUpdateView.as_view(),
        name="expense_update",
    ),
    path(
        "expenses/<int:pk>/delete/",
        views.ExpenseDeleteView.as_view(),
        name="expense_delete",
    ),
    path(
        "expenses/receipts/<int:pk>/delete/",
        views.expense_receipt_delete,
        name="expense_receipt_delete",
    ),
    path(
        "expenses/<int:pk>/link-transaction/",
        views.expense_link_transaction,
        name="expense_link_transaction",
    ),
    path(
        "expenses/<int:pk>/unlink-transaction/<int:transaction_pk>/",
        views.expense_unlink_transaction,
        name="expense_unlink_transaction",
    ),
    path(
        "expenses/<int:pk>/merge/",
        views.expense_merge,
        name="expense_merge",
    ),
    path("analytics/", views.analytics_dashboard, name="analytics"),
    # P-004: practice_analysis redirect to analytics capacity tab
    path("practice-analysis/", views.practice_analysis_redirect, name="practice_analysis"),
    path("reports/revenue/", views.revenue_report, name="revenue_report"),
    path("reports/tax-summary/", views.tax_year_summary, name="tax_year_summary"),
    path("reports/tax-summary/note/", views.save_tax_year_note, name="save_tax_year_note"),
    path("reports/tax-workday-audit/", views.tax_workday_audit, name="tax_workday_audit"),
    path("reports/tax-quarter/", views.tax_quarter_overview, name="tax_quarter_overview"),
    # Google Calendar integration
    path("calendar/authorize/", views.calendar_authorize, name="calendar_authorize"),
    path(
        "calendar/oauth2callback/",
        views.calendar_oauth2callback,
        name="calendar_oauth2callback",
    ),
    path("calendar/import/", views.calendar_import, name="calendar_import"),
    path(
        "calendar/import/events/",
        views.calendar_import_events,
        name="calendar_import_events",
    ),
    # P-013: Calendar approval queue
    path(
        "calendar/approve/",
        views.calendar_approval_queue,
        name="calendar_approval_queue",
    ),
    path(
        "calendar/approve/import/",
        views.calendar_queue_import,
        name="calendar_queue_import",
    ),
    path(
        "calendar/approve/skip-duplicates/",
        views.calendar_queue_skip_duplicates,
        name="calendar_queue_skip_duplicates",
    ),
    path(
        "calendar/events/<int:pk>/skip/",
        views.calendar_queue_skip,
        name="calendar_queue_skip",
    ),
    path(
        "calendar/events/<int:pk>/quick-action/",
        views.calendar_event_quick_action,
        name="calendar_event_quick_action",
    ),
    # Tag management
    path("tags/", views.TagListView.as_view(), name="tag_list"),
    path("tags/new/", views.TagCreateView.as_view(), name="tag_create"),
    path("tags/<int:pk>/edit/", views.TagUpdateView.as_view(), name="tag_update"),
    path("tags/<int:pk>/delete/", views.TagDeleteView.as_view(), name="tag_delete"),
    # Tag API endpoints
    path("api/tags/", views.get_available_tags, name="get_available_tags"),
    path(
        "api/clients/<int:client_id>/tags/add/",
        views.client_add_tag,
        name="client_add_tag",
    ),
    path(
        "api/clients/<int:client_id>/tags/<int:tag_id>/remove/",
        views.client_remove_tag,
        name="client_remove_tag",
    ),
    # TODO management
    path("todos/", views.TodoListView.as_view(), name="todo_list"),
    path("todos/new/", views.TodoCreateView.as_view(), name="todo_create"),
    path("todos/<int:pk>/edit/", views.TodoUpdateView.as_view(), name="todo_edit"),
    path("todos/<int:pk>/delete/", views.TodoDeleteView.as_view(), name="todo_delete"),
    path("todos/<int:pk>/toggle/", views.todo_toggle_complete, name="todo_toggle"),
    path("todos/<int:pk>/toggle-focus/", views.todo_toggle_focus, name="todo_toggle_focus"),
    # Bank statement import
    path("bank/import/", views.BankImportView.as_view(), name="bank_import"),
    path("bank/review/", views.BankReviewView.as_view(), name="bank_review"),
    path(
        "bank/expenses/",
        views.BankExpenseReviewView.as_view(),
        name="bank_expense_review",
    ),
    path(
        "bank/withdrawals/",
        views.BankWithdrawalReviewView.as_view(),
        name="bank_withdrawal_review",
    ),
    path(
        "bank/transactions/<int:pk>/",
        views.bank_transaction_detail,
        name="bank_transaction_detail",
    ),
    # Global search
    path("api/search/", views.global_search, name="global_search"),
    # Operational checklist (P-012)
    path(
        "backups/checklist/<str:checklist_type>/",
        views.OperationalChecklistView.as_view(),
        name="checklist",
    ),
    path(
        "backups/checklist/<str:checklist_type>/complete/",
        views.checklist_complete,
        name="checklist_complete",
    ),
    path(
        "backups/checklist/<str:checklist_type>/pause/<str:item_id>/",
        views.checklist_pause_item,
        name="checklist_pause",
    ),
    path(
        "backups/checklist/<str:checklist_type>/unpause/<str:item_id>/",
        views.checklist_unpause_item,
        name="checklist_unpause",
    ),
    # Email text boilerplate (P-033)
    path("tools/boilerplate/", views.boilerplate_view, name="boilerplate"),
    # Clinical documentation (P-009)
    path(
        "clients/<int:pk>/documentation/save/",
        views.client_profile_save,
        name="client_profile_save",
    ),
    path(
        "clients/<int:pk>/sessions/new/",
        views.session_log_create,
        name="session_log_create",
    ),
    path(
        "clients/<int:client_pk>/sessions/<int:log_pk>/edit/",
        views.session_log_edit,
        name="session_log_edit",
    ),
    path(
        "clients/<int:client_pk>/sessions/<int:log_pk>/delete/",
        views.session_log_delete,
        name="session_log_delete",
    ),
    path(
        "clients/<int:pk>/sessions/<int:session_pk>/duration/",
        views.session_duration_edit,
        name="session_duration_edit",
    ),
    path(
        "clients/<int:client_pk>/sessions/<int:session_pk>/delete-session/",
        views.session_delete,
        name="session_delete",
    ),
    path(
        "clients/<int:client_pk>/sessions/<int:session_pk>/toggle-billable/",
        views.session_toggle_billable,
        name="session_toggle_billable",
    ),
    path(
        "clients/<int:client_pk>/sessions/<int:log_pk>/noshow/",
        views.session_log_mark_noshow,
        name="session_log_mark_noshow",
    ),
    path(
        "clients/<int:pk>/sessions/<int:session_pk>/bill/",
        views.session_bill,
        name="session_bill",
    ),
    path(
        "clients/<int:client_pk>/sessions/<int:session_pk>/gebueh/",
        views.gebueh_leistung_create,
        name="gebueh_leistung_create",
    ),
    path(
        "clients/<int:pk>/supervision/new/",
        views.supervision_item_create,
        name="supervision_item_create",
    ),
    path(
        "clients/<int:pk>/supervision/<int:item_pk>/toggle/",
        views.supervision_item_toggle,
        name="supervision_item_toggle",
    ),
    path(
        "clients/<int:pk>/supervision/<int:item_pk>/delete/",
        views.supervision_item_delete,
        name="supervision_item_delete",
    ),
    path("supervision/", views.supervision_queue, name="supervision_queue"),
    path("clients/triage/", views.client_triage_summary, name="client_triage"),
    path(
        "clients/<int:pk>/notes/add/",
        views.client_note_create,
        name="client_note_create",
    ),
    path(
        "clients/<int:pk>/notes/<int:note_pk>/update/",
        views.client_note_update,
        name="client_note_update",
    ),
    path(
        "clients/<int:pk>/notes/<int:note_pk>/delete/",
        views.client_note_delete,
        name="client_note_delete",
    ),
]
