"""
Learned expense categorization rules for bank-statement counterparties.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from .base import PracticeScopedManager, TimestampedModel
from .financial import CompanyExpense


class ExpenseCategoryRule(TimestampedModel):
    """
    Remembers which CompanyExpense category a bank-statement counterparty maps to.

    Created/updated automatically whenever a user assigns or corrects a category
    for a bank-sourced expense (see BankExpenseReviewView and ExpenseUpdateView),
    then consulted by BankStatementImporter to pre-fill the category the next
    time a transaction from the same counterparty is imported.
    """

    practice = models.ForeignKey(
        "Practice",
        on_delete=models.PROTECT,
        related_name="expense_category_rules",
        verbose_name=_("Practice"),
    )
    match_key = models.CharField(
        max_length=200,
        verbose_name=_("Counterparty"),
        help_text=_(
            "Normalized IBAN ('iban:...') or payer name ('name:...') used to "
            "match future transactions"
        ),
    )
    category = models.CharField(
        max_length=30,
        choices=CompanyExpense.CATEGORY_CHOICES,
        verbose_name=_("Category"),
    )

    objects = PracticeScopedManager()

    class Meta:
        unique_together = [["practice", "match_key"]]
        verbose_name = _("Expense category rule")
        verbose_name_plural = _("Expense category rules")

    def __str__(self) -> str:
        return f"{self.match_key} → {self.get_category_display()}"
