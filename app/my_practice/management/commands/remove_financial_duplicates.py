"""
Management command to remove duplicate CompanyExpense and CompanyWithdrawal records.

Consolidates functionality from cleanup_expense_duplicates and remove_duplicates commands.
"""

import sys

from django.core.management.base import BaseCommand
from django.db.models import Count, Model, QuerySet

from ...models import CompanyExpense, CompanyWithdrawal


class Command(BaseCommand):
    help = "Remove duplicate CompanyExpense and CompanyWithdrawal records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show duplicates without deleting",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip confirmation prompt",
        )
        parser.add_argument(
            "--year",
            type=int,
            default=None,
            help="Filter duplicates by year (default: all years)",
        )
        parser.add_argument(
            "--type",
            type=str,
            choices=["expenses", "withdrawals", "both"],
            default="both",
            help="Type of records to check (default: both)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        skip_confirm = options["yes"]
        year = options["year"]
        record_type = options["type"]

        # Build filter message
        filter_msg = []
        if year:
            filter_msg.append(f"year {year}")
        if record_type != "both":
            filter_msg.append(record_type)

        filter_str = f" ({', '.join(filter_msg)})" if filter_msg else ""

        self.stdout.write(self.style.WARNING(f"🔍 Searching for duplicates{filter_str}..."))
        self.stdout.write("")

        # Build querysets with optional filters
        expense_qs = CompanyExpense.objects.all()
        withdrawal_qs = CompanyWithdrawal.objects.all()

        if year:
            expense_qs = expense_qs.filter(date__year=year)
            withdrawal_qs = withdrawal_qs.filter(date__year=year)

        expense_duplicates = (
            self._find_duplicate_groups(expense_qs) if record_type in ["expenses", "both"] else None
        )
        withdrawal_duplicates = (
            self._find_duplicate_groups(withdrawal_qs)
            if record_type in ["withdrawals", "both"]
            else None
        )

        expense_groups = expense_duplicates.count() if expense_duplicates else 0
        withdrawal_groups = withdrawal_duplicates.count() if withdrawal_duplicates else 0

        if expense_groups == 0 and withdrawal_groups == 0:
            self.stdout.write(self.style.SUCCESS("✅ No duplicates found"))
            return

        self.stdout.write(f"📊 Found {expense_groups} duplicate expense groups")
        self.stdout.write(f"📊 Found {withdrawal_groups} duplicate withdrawal groups")
        self.stdout.write("")

        expense_to_process: list[tuple[type[Model], list[int]]] = []
        total_expense_to_delete = 0
        if expense_groups > 0:
            assert expense_duplicates is not None
            expense_to_process, total_expense_to_delete = self._display_duplicates(
                CompanyExpense, expense_duplicates, "🧾", "Expenses"
            )

        withdrawal_to_process: list[tuple[type[Model], list[int]]] = []
        total_withdrawal_to_delete = 0
        if withdrawal_groups > 0:
            assert withdrawal_duplicates is not None
            withdrawal_to_process, total_withdrawal_to_delete = self._display_duplicates(
                CompanyWithdrawal, withdrawal_duplicates, "💰", "Withdrawals"
            )

        # Dry run - just show what would be deleted
        if dry_run:
            self.stdout.write(self.style.WARNING("📋 DRY RUN - No changes made"))
            self.stdout.write(
                f"Would delete {total_expense_to_delete} expenses and {total_withdrawal_to_delete} withdrawals"
            )
            return

        # Confirmation for actual deletion
        if not skip_confirm:
            # Check if stdin is a TTY (interactive terminal)
            if sys.stdin.isatty():
                total_to_delete = total_expense_to_delete + total_withdrawal_to_delete
                response = input(f"\n⚠️  Delete {total_to_delete} duplicate records? (yes/no): ")
                if response.lower() != "yes":
                    self.stdout.write(self.style.ERROR("❌ Aborted"))
                    return
            else:
                # Non-interactive mode
                self.stdout.write(
                    self.style.WARNING("⚠️  No interactive terminal detected. Use --yes to confirm.")
                )
                self.stdout.write(self.style.ERROR("❌ Aborted"))
                return

        # Actually delete duplicates
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("🗑️  Deleting duplicates..."))

        total_expense_deleted = self._delete_duplicates(expense_to_process)
        total_withdrawal_deleted = self._delete_duplicates(withdrawal_to_process)

        self.stdout.write(
            self.style.SUCCESS(f"✅ Deleted {total_expense_deleted} expense duplicates")
        )
        self.stdout.write(
            self.style.SUCCESS(f"✅ Deleted {total_withdrawal_deleted} withdrawal duplicates")
        )

    @staticmethod
    def _find_duplicate_groups(queryset: QuerySet) -> QuerySet:
        """Group by the fields that define a duplicate, keeping only groups with >1 record."""
        return (
            queryset.values("practice_id", "date", "amount", "description")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
            .order_by("-count")
        )

    def _display_duplicates(
        self, model: type[Model], duplicate_groups: QuerySet, emoji: str, label: str
    ) -> tuple[list[tuple[type[Model], list[int]]], int]:
        """
        Print each duplicate group and return (ids to delete per group, total to delete).

        A record linked to a bank transaction, or with receipts, is a booking in
        its own right: the bank import keeps one record per transaction, so two
        payers with the same date, amount and text give two such records. Those
        are always kept, and deleting one would also null its bank link and
        cascade its receipts. Only unlinked, receipt-less copies are deleted;
        when the whole group is unlinked, the lowest id stays.
        """
        self.stdout.write(self.style.WARNING(f"{emoji} Duplicate {label}:"))

        to_process: list[tuple[type[Model], list[int]]] = []
        total_to_delete = 0
        has_receipts = hasattr(model, "receipts")

        for dup in duplicate_groups:
            annotations = {"linked": Count("bank_transactions", distinct=True)}
            if has_receipts:
                annotations["receipt_count"] = Count("receipts", distinct=True)
            records = list(
                model.objects.filter(
                    practice_id=dup["practice_id"],
                    date=dup["date"],
                    amount=dup["amount"],
                    description=dup["description"],
                )
                .annotate(**annotations)
                .order_by("id")
            )
            if not records:
                continue

            protected = [r for r in records if r.linked or getattr(r, "receipt_count", 0)]
            keep = {r.id for r in protected} or {records[0].id}
            delete_ids = [r.id for r in records if r.id not in keep]

            categories = sorted({r.category for r in records})
            self.stdout.write(
                f"  {dup['date']} | {dup['amount']}€ | {', '.join(categories)} | Count: {len(records)}"
            )
            desc_short = dup["description"][:60]
            self.stdout.write(f"    Description: {desc_short}...")

            id_details = []
            for r in records:
                detail = f"ID {r.id} ({r.category}"
                if r.linked:
                    detail += f", {r.linked} bank transaction(s)"
                if getattr(r, "receipt_count", 0):
                    detail += f", {r.receipt_count} receipt(s)"
                id_details.append(detail + ")")
            self.stdout.write(f"    Records: {', '.join(id_details)}")
            kept = ", ".join(str(i) for i in sorted(keep))
            self.stdout.write(f"      → Would keep ID {kept}, delete {len(delete_ids)}")

            if delete_ids:
                to_process.append((model, delete_ids))
                total_to_delete += len(delete_ids)

        self.stdout.write("")
        return to_process, total_to_delete

    @staticmethod
    def _delete_duplicates(groups: list[tuple[type[Model], list[int]]]) -> int:
        """Delete the ids chosen in _display_duplicates; returns the number of records deleted."""
        total_deleted = 0
        for model, ids in groups:
            # Count only the duplicates themselves, not cascaded rows.
            total_deleted += model.objects.filter(id__in=ids).delete()[1].get(model._meta.label, 0)
        return total_deleted
