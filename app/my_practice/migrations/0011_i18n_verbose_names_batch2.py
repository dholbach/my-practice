import datetime
from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models

import my_practice.models.bank_statement
import my_practice.models.financial
import my_practice.models.invoice


class Migration(migrations.Migration):
    dependencies = [
        ("my_practice", "0010_i18n_verbose_names_batch1"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="expensereceipt",
            options={
                "ordering": ["uploaded_at"],
                "verbose_name": "Receipt",
                "verbose_name_plural": "Receipts",
            },
        ),
        migrations.AlterModelOptions(
            name="gebuhziffer",
            options={
                "ordering": ["sort_order", "nummer"],
                "verbose_name": "GebüH billing code",
                "verbose_name_plural": "GebüH billing codes",
            },
        ),
        migrations.AlterModelOptions(
            name="invoice",
            options={
                "ordering": ["-invoice_date", "-invoice_number"],
                "verbose_name": "Invoice",
                "verbose_name_plural": "Invoices",
            },
        ),
        migrations.AlterModelOptions(
            name="invoiceitem",
            options={
                "ordering": ["session__session_date"],
                "verbose_name": "Invoice item",
                "verbose_name_plural": "Invoice items",
            },
        ),
        migrations.AlterModelOptions(
            name="leistungserfassung",
            options={
                "ordering": ["session__session_date", "ziffer__sort_order"],
                "verbose_name": "Service entry",
                "verbose_name_plural": "Service entries",
            },
        ),
        migrations.AlterModelOptions(
            name="taxyearnote",
            options={
                "ordering": ["-year"],
                "verbose_name": "Tax year note",
                "verbose_name_plural": "Tax year notes",
            },
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="account_iban",
            field=models.CharField(
                blank=True,
                help_text="IBAN of the source account from the CSV export – must match the practice IBAN",
                max_length=34,
                verbose_name="Account IBAN",
            ),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="amount",
            field=models.DecimalField(
                decimal_places=2,
                help_text="Transaction amount (positive=income, negative=expense)",
                max_digits=10,
                verbose_name="Amount",
            ),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="balance_after",
            field=models.DecimalField(
                decimal_places=2,
                help_text="Account balance after transaction",
                max_digits=10,
                verbose_name="Balance after transaction",
            ),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="extracted_invoice_number",
            field=models.CharField(
                blank=True,
                help_text="Invoice number extracted from reference text",
                max_length=20,
                verbose_name="Extracted invoice number",
            ),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="imported_at",
            field=models.DateTimeField(auto_now_add=True, verbose_name="Imported on"),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="linked_expense",
            field=models.ForeignKey(
                blank=True,
                help_text="CompanyExpense auto-created or manually assigned for this transaction",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bank_transactions",
                to="my_practice.companyexpense",
                verbose_name="Linked expense",
            ),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="linked_withdrawal",
            field=models.ForeignKey(
                blank=True,
                help_text="CompanyWithdrawal auto-created or manually assigned for this transaction",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bank_transactions",
                to="my_practice.companywithdrawal",
                verbose_name="Linked withdrawal",
            ),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="match_confidence",
            field=models.CharField(
                choices=[
                    (
                        my_practice.models.bank_statement.BankTransaction.Confidence["EXACT"],
                        "Exact Match",
                    ),
                    (
                        my_practice.models.bank_statement.BankTransaction.Confidence["FUZZY"],
                        "Fuzzy Match (±5€)",
                    ),
                    (
                        my_practice.models.bank_statement.BankTransaction.Confidence["MANUAL"],
                        "Manual Assignment",
                    ),
                    (
                        my_practice.models.bank_statement.BankTransaction.Confidence["IGNORED"],
                        "Ignored (Expense/Duplicate)",
                    ),
                    (
                        my_practice.models.bank_statement.BankTransaction.Confidence["UNMATCHED"],
                        "Unmatched",
                    ),
                    (
                        my_practice.models.bank_statement.BankTransaction.Confidence[
                            "AUTO_WITHDRAWAL"
                        ],
                        "Auto-Created Withdrawal",
                    ),
                    (
                        my_practice.models.bank_statement.BankTransaction.Confidence[
                            "AUTO_EXPENSE"
                        ],
                        "Auto-Created Expense",
                    ),
                    (
                        my_practice.models.bank_statement.BankTransaction.Confidence[
                            "AUTO_CONTRIBUTION"
                        ],
                        "Auto-Created Contribution (Kapitaleinlage)",
                    ),
                    (
                        my_practice.models.bank_statement.BankTransaction.Confidence[
                            "AUTO_CORRECTION"
                        ],
                        "Auto-Created Correction (Fehlbuchung)",
                    ),
                ],
                default="unmatched",
                max_length=20,
                verbose_name="Match confidence",
            ),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="matched_invoice",
            field=models.ForeignKey(
                blank=True,
                help_text="Invoice this transaction was matched to",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bank_transactions",
                to="my_practice.invoice",
                verbose_name="Matched invoice",
            ),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="notes",
            field=models.TextField(
                blank=True, help_text="Manual notes about this transaction", verbose_name="Notes"
            ),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="payer_iban",
            field=models.CharField(blank=True, max_length=34, verbose_name="Payer/payee IBAN"),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="payer_name",
            field=models.CharField(
                help_text="Name of payer/payee", max_length=200, verbose_name="Payer/payee name"
            ),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="practice",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="bank_transactions",
                to="my_practice.practice",
                verbose_name="Practice",
            ),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="processed",
            field=models.BooleanField(
                default=False,
                help_text="Whether transaction has been processed/matched",
                verbose_name="Processed",
            ),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="reference",
            field=models.TextField(
                help_text="Payment reference text", verbose_name="Payment reference"
            ),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="transaction_date",
            field=models.DateField(
                help_text="Transaction booking date", verbose_name="Booking date"
            ),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="value_date",
            field=models.DateField(help_text="Value date", verbose_name="Value date"),
        ),
        migrations.AlterField(
            model_name="companyexpense",
            name="amount",
            field=models.DecimalField(
                decimal_places=2,
                help_text="Enter amount as a positive number",
                max_digits=10,
                verbose_name="Amount",
            ),
        ),
        migrations.AlterField(
            model_name="companyexpense",
            name="category",
            field=models.CharField(
                choices=[
                    (
                        my_practice.models.financial.CompanyExpense.Category["MIETE"],
                        "Rent",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["TELEFON"],
                        "Phone",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["VERBAND"],
                        "Association / membership fees",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["VERSICHERUNG"],
                        "Insurance",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["KONTO"],
                        "Account / account fees",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["WEBSEITE"],
                        "Website / domain",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["WERBUNG"],
                        "Advertising / marketing",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["SOFTWARE"],
                        "Software",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["SELBSTERFAHRUNG"],
                        "Personal therapy (training)",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["SUPERVISION"],
                        "Supervision",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["TRAINING"],
                        "Training / continuing education",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["AUSBILDUNG_ORT"],
                        "Training location",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["GRUPPE"],
                        "Group",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["MATERIALIEN"],
                        "Materials",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["HARDWARE"],
                        "Hardware",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["LITERATUR"],
                        "Literature",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["KONGRESS"],
                        "Conference",
                    ),
                    (
                        my_practice.models.financial.CompanyExpense.Category["OTHER"],
                        "Other",
                    ),
                ],
                default=my_practice.models.financial.CompanyExpense.Category["OTHER"],
                max_length=30,
                verbose_name="Category",
            ),
        ),
        migrations.AlterField(
            model_name="companyexpense",
            name="date",
            field=models.DateField(verbose_name="Date"),
        ),
        migrations.AlterField(
            model_name="companyexpense",
            name="description",
            field=models.TextField(blank=True, verbose_name="Description"),
        ),
        migrations.AlterField(
            model_name="companyexpense",
            name="has_invoice",
            field=models.BooleanField(default=False, verbose_name="Invoice available"),
        ),
        migrations.AlterField(
            model_name="companyexpense",
            name="is_filed_in_tax_return",
            field=models.BooleanField(default=False, verbose_name="Filed in tax return"),
        ),
        migrations.AlterField(
            model_name="companyexpense",
            name="is_tax_deductible",
            field=models.BooleanField(default=True, verbose_name="Tax deductible"),
        ),
        migrations.AlterField(
            model_name="companyexpense",
            name="practice",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="expenses",
                to="my_practice.practice",
                verbose_name="Practice",
            ),
        ),
        migrations.AlterField(
            model_name="companywithdrawal",
            name="amount",
            field=models.DecimalField(
                decimal_places=2,
                help_text="Negative amount for corrections/reversals",
                max_digits=10,
                verbose_name="Amount",
            ),
        ),
        migrations.AlterField(
            model_name="companywithdrawal",
            name="category",
            field=models.CharField(
                choices=[
                    (
                        my_practice.models.financial.CompanyWithdrawal.Category["SALARY"],
                        "Salary / personal",
                    ),
                    (
                        my_practice.models.financial.CompanyWithdrawal.Category["TAX"],
                        "Tax prepayment",
                    ),
                    (
                        my_practice.models.financial.CompanyWithdrawal.Category["PRIVATE_TRANSFER"],
                        "Private transfer",
                    ),
                    (
                        my_practice.models.financial.CompanyWithdrawal.Category["OTHER"],
                        "Other",
                    ),
                    (
                        my_practice.models.financial.CompanyWithdrawal.Category["CONTRIBUTION"],
                        "Capital contribution",
                    ),
                    (
                        my_practice.models.financial.CompanyWithdrawal.Category["CORRECTION"],
                        "Incorrect posting / correction",
                    ),
                ],
                default=my_practice.models.financial.CompanyWithdrawal.Category["SALARY"],
                max_length=20,
                verbose_name="Category",
            ),
        ),
        migrations.AlterField(
            model_name="companywithdrawal",
            name="date",
            field=models.DateField(verbose_name="Date"),
        ),
        migrations.AlterField(
            model_name="companywithdrawal",
            name="description",
            field=models.TextField(blank=True, help_text="Optional: purpose", verbose_name="Notes"),
        ),
        migrations.AlterField(
            model_name="companywithdrawal",
            name="practice",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="withdrawals",
                to="my_practice.practice",
                verbose_name="Practice",
            ),
        ),
        migrations.AlterField(
            model_name="expensereceipt",
            name="expense",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="receipts",
                to="my_practice.companyexpense",
                verbose_name="Expense",
            ),
        ),
        migrations.AlterField(
            model_name="expensereceipt",
            name="file",
            field=models.FileField(
                help_text="PDF, JPG or PNG of the receipt / invoice",
                upload_to=my_practice.models.financial.expense_attachment_upload_path,
                verbose_name="File",
            ),
        ),
        migrations.AlterField(
            model_name="gebuhziffer",
            name="anmerkung",
            field=models.TextField(
                blank=True,
                help_text="Billing notes (e.g. standalone service, frequency restriction)",
                verbose_name="Note",
            ),
        ),
        migrations.AlterField(
            model_name="gebuhziffer",
            name="bezeichnung",
            field=models.CharField(max_length=300, verbose_name="Description"),
        ),
        migrations.AlterField(
            model_name="gebuhziffer",
            name="bezugszeitraum_tage",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Period in days for the frequency check",
                null=True,
                verbose_name="Reference period (days)",
            ),
        ),
        migrations.AlterField(
            model_name="gebuhziffer",
            name="max_haeufigkeit",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Maximum count within the reference period",
                null=True,
                verbose_name="Max. frequency",
            ),
        ),
        migrations.AlterField(
            model_name="gebuhziffer",
            name="nummer",
            field=models.CharField(max_length=10, unique=True, verbose_name="Code"),
        ),
        migrations.AlterField(
            model_name="gebuhziffer",
            name="satz_max",
            field=models.DecimalField(
                decimal_places=2,
                help_text="Used for billing",
                max_digits=8,
                verbose_name="Maximum rate (€)",
            ),
        ),
        migrations.AlterField(
            model_name="gebuhziffer",
            name="satz_min",
            field=models.DecimalField(
                decimal_places=2,
                help_text="Reference value, not billed",
                max_digits=8,
                verbose_name="Minimum rate (€)",
            ),
        ),
        migrations.AlterField(
            model_name="gebuhziffer",
            name="sort_order",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="Display order in the quick-entry list",
                verbose_name="Order",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="client",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="invoices",
                to="my_practice.client",
                verbose_name="Client",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="invoice_date",
            field=models.DateField(
                default=datetime.date.today,
                help_text="Defaults to today",
                verbose_name="Invoice date",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="invoice_number",
            field=models.CharField(
                blank=True,
                help_text="Auto-generated (e.g., JL-5) or enter manually",
                max_length=20,
                unique=True,
                verbose_name="Invoice number",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="notes",
            field=models.TextField(blank=True, verbose_name="Notes"),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="paid_date",
            field=models.DateField(
                blank=True, help_text="Date of payment", null=True, verbose_name="Paid on"
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="practice",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="invoices",
                to="my_practice.practice",
                verbose_name="Practice",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="status",
            field=models.CharField(
                choices=[
                    (my_practice.models.invoice.Invoice.Status["DRAFT"], "Draft"),
                    (my_practice.models.invoice.Invoice.Status["SENT"], "Sent"),
                    (my_practice.models.invoice.Invoice.Status["PAID"], "Paid"),
                    (my_practice.models.invoice.Invoice.Status["CANCELLED"], "Cancelled"),
                    (my_practice.models.invoice.Invoice.Status["WRITTEN_OFF"], "Written off"),
                ],
                default=my_practice.models.invoice.Invoice.Status["DRAFT"],
                max_length=20,
                verbose_name="Status",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="subtotal",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0.00"), max_digits=10, verbose_name="Subtotal"
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="tax_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=10,
                verbose_name="Tax amount",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="tax_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Kleinunternehmer = 0%",
                max_digits=5,
                verbose_name="Tax rate (%)",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="total",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=10,
                verbose_name="Total amount",
            ),
        ),
        migrations.AlterField(
            model_name="invoiceitem",
            name="group_size",
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text="Number of participants for group offerings (default 1 = individual session). Affects the calculation of therapist hours in analytics.",
                verbose_name="Group size",
            ),
        ),
        migrations.AlterField(
            model_name="invoiceitem",
            name="rate",
            field=models.DecimalField(decimal_places=2, max_digits=6, verbose_name="Rate"),
        ),
        migrations.AlterField(
            model_name="invoiceitem",
            name="session",
            field=models.ForeignKey(
                help_text="Linked session (central reference for clinical documentation + billing)",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="invoice_items",
                to="my_practice.session",
                verbose_name="Session",
            ),
        ),
        migrations.AlterField(
            model_name="leistungserfassung",
            name="betrag",
            field=models.DecimalField(
                decimal_places=2,
                help_text="= maximum rate of the billing code at the time of entry",
                max_digits=8,
                verbose_name="GebüH amount (€)",
            ),
        ),
        migrations.AlterField(
            model_name="leistungserfassung",
            name="session",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="gebueh_leistungen",
                to="my_practice.session",
                verbose_name="Session",
            ),
        ),
        migrations.AlterField(
            model_name="leistungserfassung",
            name="vereinbarter_betrag",
            field=models.DecimalField(
                decimal_places=2,
                help_text="Fee for the session (hourly_rate × duration/60), frozen at entry time",
                max_digits=8,
                verbose_name="Agreed amount (€)",
            ),
        ),
        migrations.AlterField(
            model_name="leistungserfassung",
            name="ziffer",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="leistungen",
                to="my_practice.gebuhziffer",
                verbose_name="GebüH billing code",
            ),
        ),
        migrations.AlterField(
            model_name="taxyearnote",
            name="allocation_note",
            field=models.TextField(
                blank=True,
                help_text='Documented split key, e.g. "Revenue share 95/5 for 2025 — HO allowance and commuter allowance split accordingly."',
                verbose_name="Allocation note",
            ),
        ),
        migrations.AlterField(
            model_name="taxyearnote",
            name="practice",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tax_year_notes",
                to="my_practice.practice",
                verbose_name="Practice",
            ),
        ),
        migrations.AlterField(
            model_name="taxyearnote",
            name="settlement_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Positive = back payment to the tax office, negative = refund from the tax office",
                max_digits=10,
                null=True,
                verbose_name="Tax back payment / refund",
            ),
        ),
        migrations.AlterField(
            model_name="taxyearnote",
            name="settlement_date",
            field=models.DateField(
                blank=True,
                help_text="Date of the tax assessment notice",
                null=True,
                verbose_name="Assessment date",
            ),
        ),
        migrations.AlterField(
            model_name="taxyearnote",
            name="year",
            field=models.PositiveSmallIntegerField(db_index=True, verbose_name="Tax year"),
        ),
        migrations.AlterConstraint(
            model_name="invoice",
            name="unique_invoice_number",
            constraint=models.UniqueConstraint(
                fields=("invoice_number",),
                name="unique_invoice_number",
                violation_error_message="This invoice number already exists.",
            ),
        ),
    ]
