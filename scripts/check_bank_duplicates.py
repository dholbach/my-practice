"""Check for duplicate BankTransactions."""

import os
import sys

import django

# Same bootstrap as create_default_tags.py. ./dev.py run pipes this file into
# `manage.py shell` inside the container, where /app is already importable, but
# the path insert keeps the script runnable on its own the way its neighbour is.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db.models import Count  # noqa: E402

from my_practice.models import BankTransaction  # noqa: E402

# Find duplicates based on unique constraint
duplicates = (
    BankTransaction.objects.values("practice_id", "transaction_date", "amount", "reference")
    .annotate(count=Count("id"))
    .filter(count__gt=1)
    .order_by("-count")
)

if duplicates:
    print(f"Found {duplicates.count()} duplicate groups:")
    for dup in duplicates:
        print(
            f"\n  Practice: {dup['practice_id']}, Date: {dup['transaction_date']}, "
            f"Amount: {dup['amount']}, Count: {dup['count']}"
        )
        print(f"  Reference: {dup['reference'][:80]}...")

        # Show actual records
        records = BankTransaction.objects.filter(
            practice_id=dup["practice_id"],
            transaction_date=dup["transaction_date"],
            amount=dup["amount"],
            reference=dup["reference"],
        )
        for rec in records:
            print(f"    ID: {rec.id}, Match: {rec.match_confidence}, Processed: {rec.processed}")
else:
    print("No duplicate BankTransactions found.")
