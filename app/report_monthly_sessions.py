"""
Monthly session hours + revenue report.

Usage:  ./dev.py run report_monthly_sessions.py

Prints a table of every month with:
  - therapist hours (group_size-corrected)
  - raw billing hours (sum of all item hours, no group_size correction)
  - paid revenue
  - capacity hours (from capacity_trends)
  - utilisation %
"""

from collections import defaultdict

from my_practice.models import InvoiceItem
from my_practice.utils import count_sessions, format_month_key, format_month_label
from my_practice.utils.capacity_helpers import get_capacity_trends

# ── 1. Collect InvoiceItem data grouped by month ───────────────────────────
items_qs = InvoiceItem.objects.select_related("invoice", "session").order_by(
    "session__session_date"
)

month_data: dict[str, dict] = {}

for item in items_qs:
    if not item.session_id:
        continue
    key = format_month_key(item.session.session_date)
    if key not in month_data:
        month_data[key] = {"items": [], "revenue": 0.0}
    month_data[key]["items"].append(item)
    if item.invoice.status == "paid" and not item.session.cancelled:
        month_data[key]["revenue"] += float(item.total)

# ── 2. Pull capacity trends (already accounts for vacation + capacity periods) ──
capacity_by_month = {
    f"{ct['year']}-{ct['month_num']:02d}": ct for ct in get_capacity_trends(start_year=2020)
}

# ── 3. Print table ─────────────────────────────────────────────────────────
HEADER = (
    f"{'Month':<12} {'TherapH':>8} {'BillingH':>9} {'Revenue':>10} "
    f"{'CapacityH':>10} {'Util%':>6}  Notes"
)
print(HEADER)
print("-" * len(HEADER))

for key in sorted(month_data.keys()):
    d = month_data[key]
    items = d["items"]
    revenue = d["revenue"]

    therapist_h = count_sessions(items, exclude_cancellations=True, therapist_hours=True)
    billing_h = count_sessions(items, exclude_cancellations=True, therapist_hours=False)

    ct = capacity_by_month.get(key, {})
    capacity_h = ct.get("capacity_hours", 0.0)
    util_pct = ct.get("capacity_percentage", 0)
    timeoff = ct.get("timeoff_days", 0)

    notes = f"🏖️ {timeoff}d off" if timeoff else ""
    diff = billing_h - therapist_h
    if diff > 0.1:
        notes += f"  [group: -{diff:.1f}h billing]"

    label = format_month_label(key, "medium")
    print(
        f"{label:<12} {therapist_h:>8.1f} {billing_h:>9.1f} {revenue:>10,.0f} €"
        f" {capacity_h:>9.1f}h {util_pct:>5}%  {notes}"
    )

# ── 4. Seasonality summary ─────────────────────────────────────────────────
print()
print("── Seasonality (avg over years with bookings) ──")
MONTHS_DE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

by_month_num: dict[int, list] = defaultdict(list)
for key, ct in capacity_by_month.items():
    d = month_data.get(key)
    if d and ct["booked_hours"] > 0:
        by_month_num[ct["month_num"]].append(ct)

for m in range(1, 13):
    entries = by_month_num.get(m, [])
    if not entries:
        print(f"  {MONTHS_DE[m - 1]:<4}  no data")
        continue
    avg_pct = sum(e["capacity_percentage"] for e in entries) / len(entries)
    avg_booked = sum(e["booked_hours"] for e in entries) / len(entries)
    avg_cap = sum(e["capacity_hours"] for e in entries) / len(entries)
    years = sorted({e["year"] for e in entries})
    print(
        f"  {MONTHS_DE[m - 1]:<4}  {avg_pct:5.1f}%  "
        f"Ø {avg_booked:.1f}h / {avg_cap:.1f}h  "
        f"({len(entries)}×: {', '.join(str(y) for y in years)})"
    )
