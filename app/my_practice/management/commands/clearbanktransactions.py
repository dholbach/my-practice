"""
Management command to clear bank transactions for reimporting.
"""

import sys
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from ...models import BankTransaction, CompanyExpense, CompanyWithdrawal


class Command(BaseCommand):
    help = "Clear bank transactions to allow fresh reimport"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Delete all transactions (including processed ones)",
        )
        parser.add_argument(
            "--since",
            type=str,
            metavar="YYYY-MM-DD",
            help="Delete transactions with transaction_date >= this date (e.g. 2026-01-01 for all of 2026)",
        )
        parser.add_argument(
            "--imported-on",
            type=str,
            metavar="YYYY-MM-DD",
            help="Delete only transactions imported on this date (useful for removing a bad import batch)",
        )
        parser.add_argument(
            "--today",
            action="store_true",
            help="Shorthand for --imported-on today",
        )
        parser.add_argument(
            "--with-financials",
            action="store_true",
            help=(
                "Also delete CompanyExpense and CompanyWithdrawal records linked to the selected "
                "transactions (via linked_expense/linked_withdrawal FK, or created on the same "
                "import date when using --imported-on/--today)"
            ),
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip confirmation prompt",
        )

    # ── public entry point ────────────────────────────────────────────────────

    def handle(self, *args, **options):
        transactions, scope = self._resolve_filter(options)
        expenses_qs, withdrawals_qs = self._collect_financials(transactions, options)

        self.stdout.write("")

        count = transactions.count()
        expense_count = expenses_qs.count() if expenses_qs is not None else 0
        withdrawal_count = withdrawals_qs.count() if withdrawals_qs is not None else 0

        if count == 0 and expense_count == 0 and withdrawal_count == 0:
            self.stdout.write(self.style.ERROR(f"❌ No {scope} entries found"))
            return

        self._print_preview(transactions, expenses_qs, withdrawals_qs, scope)

        total = count + expense_count + withdrawal_count
        if not self._confirm(total, options["yes"]):
            return

        self._perform_deletion(transactions, expenses_qs, withdrawals_qs)
        self.stdout.write("💡 You can now import the correct bank CSV.")

    # ── filter resolution ─────────────────────────────────────────────────────

    def _resolve_filter(self, options):
        """Return (queryset, scope_label) based on CLI options."""
        since_str = options.get("since")
        imported_on_str = options.get("imported_on")
        with_financials = options.get("with_financials", False)

        if since_str:
            try:
                since_date = date.fromisoformat(since_str)
            except ValueError:
                raise CommandError(f"Invalid date: {since_str}. Expected: YYYY-MM-DD")
            self.stdout.write(f"ℹ️  Deleting transactions with date >= {since_date}")
            self._print_financials_tip(with_financials)
            return (
                BankTransaction.objects.filter(transaction_date__gte=since_date),
                f"transactions from {since_date}",
            )

        if options.get("today"):
            today = date.today()
            self.stdout.write(f"ℹ️  Deleting transactions imported on {today}")
            self._print_financials_tip(with_financials)
            return (
                BankTransaction.objects.filter(imported_at__date=today),
                f"imported on {today}",
            )

        if imported_on_str:
            try:
                import_date = date.fromisoformat(imported_on_str)
            except ValueError:
                raise CommandError(f"Invalid date: {imported_on_str}. Expected: YYYY-MM-DD")
            self.stdout.write(f"ℹ️  Deleting transactions imported on {import_date}")
            self._print_financials_tip(with_financials)
            return (
                BankTransaction.objects.filter(imported_at__date=import_date),
                f"imported on {import_date}",
            )

        if options["all"]:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  --all flag: deleting ALL transactions (including processed ones)"
                )
            )
            return BankTransaction.objects.all(), "all"

        self.stdout.write("ℹ️  Deleting unprocessed transactions only (processed=False)")
        self.stdout.write("   Use --all to delete all transactions")
        return BankTransaction.objects.filter(processed=False), "unprocessed"

    def _print_financials_tip(self, with_financials: bool) -> None:
        if with_financials:
            self.stdout.write("ℹ️  --with-financials: also deleting linked expenses and withdrawals")
        else:
            self.stdout.write(
                "💡 Tip: --with-financials also deletes linked expenses and withdrawals"
            )

    # ── financial record collection ───────────────────────────────────────────

    def _collect_financials(self, transactions, options):
        """Return (expenses_qs, withdrawals_qs) or (None, None) if not requested."""
        if not options.get("with_financials"):
            return None, None

        since_str = options.get("since")
        imported_on_str = options.get("imported_on")
        use_today = options.get("today")

        if since_str:
            # Evaluate IDs eagerly before transactions are deleted — a lazy subquery
            # would return nothing after the transactions queryset is deleted.
            expense_ids = list(
                transactions.filter(linked_expense__isnull=False).values_list(
                    "linked_expense_id", flat=True
                )
            )
            withdrawal_ids = list(
                transactions.filter(linked_withdrawal__isnull=False).values_list(
                    "linked_withdrawal_id", flat=True
                )
            )
            return (
                CompanyExpense.objects.filter(id__in=expense_ids),
                CompanyWithdrawal.objects.filter(id__in=withdrawal_ids),
            )

        if use_today or imported_on_str:
            # Fall back to created_at date for --imported-on (covers pre-FK records)
            import_date = date.today() if use_today else date.fromisoformat(imported_on_str)
            return (
                CompanyExpense.objects.filter(created_at__date=import_date),
                CompanyWithdrawal.objects.filter(created_at__date=import_date),
            )

        # --all and default (unprocessed) modes don't support --with-financials by date
        return None, None

    # ── preview output ────────────────────────────────────────────────────────

    def _print_preview(self, transactions, expenses_qs, withdrawals_qs, scope: str) -> None:
        count = transactions.count()
        if count > 0:
            self._print_section(
                f"{scope} transactions",
                transactions,
                count,
                lambda t: (
                    f"{t.transaction_date}: "
                    f"{t.payer_name[:30] if len(t.payer_name) > 30 else t.payer_name} | "
                    f"{t.amount}€ | {t.match_confidence}"
                ),
            )

        if expenses_qs is not None:
            expense_count = expenses_qs.count()
            if expense_count > 0:
                self._print_section(
                    "linked expenses",
                    expenses_qs,
                    expense_count,
                    lambda e: (
                        f"{e.date}: {e.amount}€ | "
                        f"{e.description[:50] if len(e.description) > 50 else e.description}"
                    ),
                )

        if withdrawals_qs is not None:
            withdrawal_count = withdrawals_qs.count()
            if withdrawal_count > 0:
                self._print_section(
                    "linked withdrawals",
                    withdrawals_qs,
                    withdrawal_count,
                    lambda w: (
                        f"{w.date}: {w.amount}€ | "
                        f"{w.description[:50] if len(w.description) > 50 else w.description}"
                    ),
                )

    def _print_section(self, label: str, queryset, count: int, formatter) -> None:
        self.stdout.write(f"📋 {count} {label}")
        for item in queryset[:10]:
            self.stdout.write(f"  - {formatter(item)}")
        if count > 10:
            self.stdout.write(f"  ... and {count - 10} more")
        self.stdout.write("")

    # ── confirmation ──────────────────────────────────────────────────────────

    def _confirm(self, total: int, skip_confirm: bool) -> bool:
        if skip_confirm:
            return True
        if not sys.stdin.isatty():
            self.stdout.write(
                self.style.WARNING("⚠️  No interactive terminal detected. Use --yes to confirm.")
            )
            self.stdout.write(self.style.ERROR("❌ Aborted"))
            return False
        response = input(f"⚠️  Delete {total} entries? (yes/no): ")
        if response.lower() != "yes":
            self.stdout.write(self.style.ERROR("❌ Aborted"))
            return False
        return True

    # ── deletion ──────────────────────────────────────────────────────────────

    def _perform_deletion(self, transactions, expenses_qs, withdrawals_qs) -> None:
        if transactions.exists():
            deleted_count, _ = transactions.delete()
            self.stdout.write(self.style.SUCCESS(f"✅ {deleted_count} transactions deleted"))
        if expenses_qs is not None and expenses_qs.exists():
            deleted_exp, _ = expenses_qs.delete()
            self.stdout.write(self.style.SUCCESS(f"✅ {deleted_exp} expenses deleted"))
        if withdrawals_qs is not None and withdrawals_qs.exists():
            deleted_wd, _ = withdrawals_qs.delete()
            self.stdout.write(self.style.SUCCESS(f"✅ {deleted_wd} withdrawals deleted"))
