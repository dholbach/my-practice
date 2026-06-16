"""
Management command to remove duplicate CompanyExpense and CompanyWithdrawal records.

Consolidates functionality from cleanup_expense_duplicates and remove_duplicates commands.
"""

import sys

from django.core.management.base import BaseCommand
from django.db.models import Count, QuerySet
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

        # Find duplicate expenses
        expense_duplicates = None
        if record_type in ["expenses", "both"]:
            expense_duplicates = (
                expense_qs.values("practice_id", "date", "amount", "description")
                .annotate(count=Count("id"))
                .filter(count__gt=1)
                .order_by("-count")
            )

        # Find duplicate withdrawals
        withdrawal_duplicates = None
        if record_type in ["withdrawals", "both"]:
            withdrawal_duplicates = (
                withdrawal_qs.values("practice_id", "date", "amount", "description")
                .annotate(count=Count("id"))
                .filter(count__gt=1)
                .order_by("-count")
            )

        expense_groups = expense_duplicates.count() if expense_duplicates else 0
        withdrawal_groups = withdrawal_duplicates.count() if withdrawal_duplicates else 0

        if expense_groups == 0 and withdrawal_groups == 0:
            self.stdout.write(self.style.SUCCESS("✅ No duplicates found"))
            return

        self.stdout.write(f"📊 Found {expense_groups} duplicate expense groups")
        self.stdout.write(f"📊 Found {withdrawal_groups} duplicate withdrawal groups")
        self.stdout.write("")

        # Collect records to process
        expense_to_process: list[QuerySet] = []
        withdrawal_to_process: list[QuerySet] = []

        total_expense_to_delete = 0
        total_withdrawal_to_delete = 0

        # Show duplicate expenses
        if expense_groups > 0:
            self.stdout.write(self.style.WARNING("🧾 Duplicate Expenses:"))
            assert expense_duplicates is not None
            for dup in expense_duplicates:
                records = CompanyExpense.objects.filter(
                    practice_id=dup["practice_id"],
                    date=dup["date"],
                    amount=dup["amount"],
                    description=dup["description"],
                ).order_by("id")

                count = records.count()
                first_record = records.first()
                if first_record is None:
                    continue

                # Show all categories involved
                categories = list(records.values_list("category", flat=True).distinct())
                category_display = ", ".join(categories) if len(categories) > 1 else categories[0]

                self.stdout.write(
                    f"  {dup['date']} | {dup['amount']}€ | {category_display} | Count: {count}"
                )
                desc_short = dup["description"][:60]
                self.stdout.write(f"    Description: {desc_short}...")

                # Show all IDs and their categories
                id_details = [f"ID {r.id} ({r.category})" for r in records]
                self.stdout.write(f"    Records: {', '.join(id_details)}")
                self.stdout.write(f"      → Would keep ID {first_record.id}, delete {count - 1}")

                expense_to_process.append(records)
                total_expense_to_delete += count - 1

            self.stdout.write("")

        # Show duplicate withdrawals
        if withdrawal_groups > 0:
            self.stdout.write(self.style.WARNING("💰 Duplicate Withdrawals:"))
            assert withdrawal_duplicates is not None
            for dup in withdrawal_duplicates:
                withdrawal_records = CompanyWithdrawal.objects.filter(
                    practice_id=dup["practice_id"],
                    date=dup["date"],
                    amount=dup["amount"],
                    description=dup["description"],
                ).order_by("id")

                count = withdrawal_records.count()
                w_first_record = withdrawal_records.first()
                if w_first_record is None:
                    continue

                # Show all categories involved
                categories = list(withdrawal_records.values_list("category", flat=True).distinct())
                category_display = ", ".join(categories) if len(categories) > 1 else categories[0]

                self.stdout.write(
                    f"  {dup['date']} | {dup['amount']}€ | {category_display} | Count: {count}"
                )
                desc_short = dup["description"][:60]
                self.stdout.write(f"    Description: {desc_short}...")

                # Show all IDs and their categories
                id_details = [f"ID {r.id} ({r.category})" for r in withdrawal_records]
                self.stdout.write(f"    Records: {', '.join(id_details)}")
                self.stdout.write(f"      → Would keep ID {w_first_record.id}, delete {count - 1}")

                withdrawal_to_process.append(withdrawal_records)
                total_withdrawal_to_delete += count - 1

            self.stdout.write("")

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

        total_expense_deleted = 0
        for exp_records in expense_to_process:
            # Keep first, delete rest
            first_rec = exp_records.first()
            if first_rec is None:
                continue
            records_to_delete = exp_records.exclude(id=first_rec.id)
            deleted = records_to_delete.delete()[0]
            total_expense_deleted += deleted

        total_withdrawal_deleted = 0
        for wdl_records in withdrawal_to_process:
            # Keep first, delete rest
            first_w_rec = wdl_records.first()
            if first_w_rec is None:
                continue
            wdl_to_delete = wdl_records.exclude(id=first_w_rec.id)
            deleted = wdl_to_delete.delete()[0]
            total_withdrawal_deleted += deleted

        self.stdout.write(
            self.style.SUCCESS(f"✅ Deleted {total_expense_deleted} expense duplicates")
        )
        self.stdout.write(
            self.style.SUCCESS(f"✅ Deleted {total_withdrawal_deleted} withdrawal duplicates")
        )
