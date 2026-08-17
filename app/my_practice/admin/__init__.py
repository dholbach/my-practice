"""
Admin package - domain-split admin configuration, mirroring models/.

All submodules are imported here so their @admin.register decorators run,
and so `from my_practice.admin import XAdmin` keeps working for callers
(e.g. tests) that imported directly from the old monolithic admin.py.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy

# Bank statement admin
from .bank_statement import BankTransactionAdmin

# Calendar admin
from .calendar import PendingCalendarEventAdmin

# Client admin
from .client import ClientAdmin, ClientDocumentInline

# Client alias admin
from .client_alias import ClientAliasAdmin

# Clinical admin
from .clinical import (
    ClientNoteAdmin,
    ClientProfileAdmin,
    SessionLogAdmin,
    SupervisionItemAdmin,
)

# Expense category rule admin
from .expense_category_rule import ExpenseCategoryRuleAdmin

# Financial admin
from .financial import CompanyExpenseAdmin, CompanyWithdrawalAdmin

# GebüH admin
from .gebueh import GebuhZifferAdmin, LeistungserfassungAdmin

# Inquiry admin
from .inquiry import ClientInquiryAdmin, MarketingPeriodAdmin

# Invoice admin
from .invoice import (
    InvoiceAdmin,
    InvoiceItemAdmin,
    InvoiceItemAdminForm,
    InvoiceItemInline,
)

# Operational checklist admin
from .operational import ChecklistItemPauseAdmin, OperationalChecklistCompletionAdmin

# Practice admin
from .practice import PracticeAdmin

# Service type admin
from .service import ServiceTypeAdmin

# Session admin
from .session import SessionAdmin

# Tag admin
from .tag import ClientTagAdmin

# Time off admin
from .timeoff import TimeOffAdmin

# Todo admin
from .todo import PracticeTodoAdmin

__all__ = [
    "BankTransactionAdmin",
    "ChecklistItemPauseAdmin",
    "ClientAdmin",
    "ClientAliasAdmin",
    "ClientDocumentInline",
    "ClientInquiryAdmin",
    "ClientNoteAdmin",
    "ClientProfileAdmin",
    "ClientTagAdmin",
    "CompanyExpenseAdmin",
    "CompanyWithdrawalAdmin",
    "ExpenseCategoryRuleAdmin",
    "GebuhZifferAdmin",
    "InvoiceAdmin",
    "InvoiceItemAdmin",
    "InvoiceItemAdminForm",
    "InvoiceItemInline",
    "LeistungserfassungAdmin",
    "MarketingPeriodAdmin",
    "OperationalChecklistCompletionAdmin",
    "PendingCalendarEventAdmin",
    "PracticeAdmin",
    "PracticeTodoAdmin",
    "ServiceTypeAdmin",
    "SessionAdmin",
    "SessionLogAdmin",
    "SupervisionItemAdmin",
    "TimeOffAdmin",
]

# Customize admin site headers
admin.site.site_header = gettext_lazy("Therapy Practice Management")
admin.site.site_title = gettext_lazy("Payments Admin")
admin.site.index_title = gettext_lazy("Welcome to Therapy Practice Management")
