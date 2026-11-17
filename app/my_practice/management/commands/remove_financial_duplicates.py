"""
Management command to remove duplicate CompanyExpense and CompanyWithdrawal records.

Consolidates functionality from cleanup_expense_duplicates and remove_duplicates commands.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Model, QuerySet

from ...models import CompanyExpense, CompanyWithdrawal
from ._confirm import confirm_deletion


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
        year = options["year"]
        record_type = options["type"]

        filter_msg = []
        if year:
            filter_msg.append(f"year {year}")
        if record_type != "both":
            filter_msg.append(record_type)
        filter_str = f" ({', '.join(filter_msg)})" if filter_msg else ""

        self.stdout.write(self.style.WARNING(f"🔍 Searching for duplicates{filter_str}..."))
        self.stdout.write("")

        expense_duplicates, withdrawal_duplicates = self._find_groups(year, record_type)
        expense_groups = expense_duplicates.count() if expense_duplicates else 0
        withdrawal_groups = withdrawal_duplicates.count() if withdrawal_duplicates else 0

        if expense_groups == 0 and withdrawal_groups == 0:
            self.stdout.write(self.style.SUCCESS("✅ No duplicates found"))
            return

        self.stdout.write(f"📊 Found {expense_groups} duplicate expense groups")
        self.stdout.write(f"📊 Found {withdrawal_groups} duplicate withdrawal groups")
        self.stdout.write("")

        expense_to_process, total_expense_to_delete = self._plan(
            CompanyExpense, expense_duplicates, "🧾", "Expenses"
        )
        withdrawal_to_process, total_withdrawal_to_delete = self._plan(
            CompanyWithdrawal, withdrawal_duplicates, "💰", "Withdrawals"
        )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("📋 DRY RUN - No changes made"))
            self.stdout.write(
                f"Would delete {total_expense_to_delete} expenses and {total_withdrawal_to_delete} withdrawals"
            )
            return

        total_to_delete = total_expense_to_delete + total_withdrawal_to_delete
        if not confirm_deletion(
            self, f"\n⚠️  Delete {total_to_delete} duplicate records? (yes/no): ", options["yes"]
        ):
            return

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

    def _find_groups(
        self, year: int | None, record_type: str
    ) -> tuple[QuerySet | None, QuerySet | None]:
        """Duplicate groups of expenses and of withdrawals; None for a type not asked for."""
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
        return expense_duplicates, withdrawal_duplicates

    def _plan(
        self, model: type[Model], groups: QuerySet | None, emoji: str, label: str
    ) -> tuple[list[tuple[type[Model], list[int]]], int]:
        """Print the groups of one record type and return what would be deleted ([], 0 if none)."""
        if not groups or groups.count() == 0:
            return [], 0
        return self._display_duplicates(model, groups, emoji, label)

    @staticmethod
    def _find_duplicate_groups(queryset: QuerySet) -> QuerySet:
        """Group by the fields that define a duplicate, keeping only groups with >1 record."""
        return (
            queryset.values("practice_id", "date", "amount", "description")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
            .order_by("-count")
        )

    @staticmethod
    def _choose_deletions(records: list) -> tuple[set[int], list[int]]:
        """Which ids of one duplicate group stay and which go (``records`` ordered by id)."""
        protected = [r for r in records if r.linked or getattr(r, "receipt_count", 0)]
        keep = {r.id for r in protected} or {records[0].id}
        return keep, [r.id for r in records if r.id not in keep]

    def _print_group(self, dup: dict, records: list, keep: set[int], delete_ids: list[int]) -> None:
        """Print one duplicate group: its records, what ties them to other data, the decision."""
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

            keep, delete_ids = self._choose_deletions(records)
            self._print_group(dup, records, keep, delete_ids)

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
