"""
Tests for TimeOff calculation utilities.
"""

from datetime import date

from django.test import TestCase
from my_practice.models import Practice, TimeOff
from my_practice.utils.date_helpers import DateRangeHelper
from my_practice.utils.timeoff_helpers import (
    calculate_timeoff_for_period,
    calculate_timeoff_for_year,
)


class DateRangeHelperYearOverlapTestCase(TestCase):
    """Tests for DateRangeHelper.calculate_year_overlap_days"""

    def test_period_entirely_in_year(self):
        """Period completely within target year"""
        result = DateRangeHelper.calculate_year_overlap_days(
            date(2025, 8, 9), date(2025, 8, 25), 2025
        )
        self.assertEqual(result, 17)

    def test_period_spans_year_boundary_start(self):
        """Period starts in previous year, ends in target year"""
        result = DateRangeHelper.calculate_year_overlap_days(
            date(2024, 12, 23), date(2025, 1, 5), 2025
        )
        self.assertEqual(result, 5)  # Jan 1-5 = 5 days

    def test_period_spans_year_boundary_end(self):
        """Period starts in target year, ends in next year"""
        result = DateRangeHelper.calculate_year_overlap_days(
            date(2025, 12, 22), date(2026, 1, 5), 2025
        )
        self.assertEqual(result, 10)  # Dec 22-31 = 10 days

    def test_period_no_overlap_before_year(self):
        """Period completely before target year"""
        result = DateRangeHelper.calculate_year_overlap_days(
            date(2024, 1, 1), date(2024, 12, 31), 2025
        )
        self.assertEqual(result, 0)

    def test_period_no_overlap_after_year(self):
        """Period completely after target year"""
        result = DateRangeHelper.calculate_year_overlap_days(
            date(2026, 1, 1), date(2026, 12, 31), 2025
        )
        self.assertEqual(result, 0)

    def test_single_day_in_year(self):
        """Single day period in target year"""
        result = DateRangeHelper.calculate_year_overlap_days(
            date(2025, 6, 15), date(2025, 6, 15), 2025
        )
        self.assertEqual(result, 1)

    def test_year_as_date_object(self):
        """Pass target_year as date object instead of int"""
        result = DateRangeHelper.calculate_year_overlap_days(
            date(2025, 8, 9), date(2025, 8, 25), date(2025, 6, 15)
        )
        self.assertEqual(result, 17)


class CalculateTimeoffForYearTestCase(TestCase):
    """Tests for calculate_timeoff_for_year function"""

    def setUp(self):
        """Create test TimeOff entries"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="timeoff_helpers-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Create timeoff entries for 2025
        self.winter_holiday = TimeOff.objects.create(
            title="Winter Holidays",
            type="vacation",
            start_date=date(2025, 2, 7),
            end_date=date(2025, 2, 14),
        )

        self.summer_holiday = TimeOff.objects.create(
            title="Summer Holidays",
            type="vacation",
            start_date=date(2025, 8, 9),
            end_date=date(2025, 8, 25),
        )

        # This crosses year boundary
        self.xmas_2024_2025 = TimeOff.objects.create(
            title="Christmas + New Year",
            type="holiday",
            start_date=date(2024, 12, 23),
            end_date=date(2025, 1, 5),
        )

        # This crosses year boundary
        self.xmas_2025_2026 = TimeOff.objects.create(
            title="Christmas + New Year",
            type="holiday",
            start_date=date(2025, 12, 22),
            end_date=date(2026, 1, 5),
        )

        self.sick_leave = TimeOff.objects.create(
            title="Sick Leave",
            type="sick",
            start_date=date(2025, 5, 5),
            end_date=date(2025, 5, 8),
        )

    def test_calculate_total_days_for_year(self):
        """Total days off should only count days in the specified year"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        result = calculate_timeoff_for_year(2025)

        # Expected:
        # - Winter: 8 days
        # - Summer: 17 days
        # - Xmas 2024-2025: 5 days (Jan 1-5)
        # - Xmas 2025-2026: 10 days (Dec 22-31)
        # - Sick: 4 days
        # Total: 44 days
        self.assertEqual(result["total_days"], 44)

    def test_calculate_weeks_for_year(self):
        """Weeks should be calculated as days / 7"""
        result = calculate_timeoff_for_year(2025)
        # 44 days / 7 = 6.3 weeks
        self.assertEqual(result["total_weeks"], 6.3)

    def test_calculate_workdays_for_year(self):
        """Workdays should exclude public holidays, not just count Mon–Fri"""
        result = calculate_timeoff_for_year(2025)
        # Non-holiday working days per entry (in 2025):
        # - Winter (Feb 7-14): 6 (no holidays in range)
        # - Summer (Aug 9-25): 11 (no Berlin holidays in range)
        # - Xmas 2024-25 (Jan 1-5 in 2025): 2 (Jan 1 = Neujahr excluded; Jan 2,3 = 2 days)
        # - Xmas 2025-26 (Dec 22-31 in 2025): 6 (Dec 25+26 Weihnachten excluded; 8−2=6)
        # - Sick (May 5-8): 4 (no holidays in range)
        # Total: 29
        self.assertEqual(result["total_workdays"], 29)

    def test_entries_detail(self):
        """Returned entries should have correct details"""
        result = calculate_timeoff_for_year(2025)
        self.assertEqual(len(result["entries"]), 5)

        # Find the spanning entry (2024-12-23 to 2025-01-05)
        xmas_2024_entries = [
            e
            for e in result["entries"]
            if e["title"] == "Christmas + New Year" and e["full_start"].year == 2024
        ]
        self.assertEqual(len(xmas_2024_entries), 1)
        xmas_2024_entry = xmas_2024_entries[0]
        self.assertEqual(xmas_2024_entry["period_days"], 5)
        # Spanned year means it starts in one year and ends in another
        self.assertTrue(xmas_2024_entry["full_start"].year != xmas_2024_entry["full_end"].year)

    def test_calculate_for_previous_year(self):
        """Should handle calculation for non-current years"""
        result = calculate_timeoff_for_year(2024)

        # Only the 2024-12-23 to 2025-01-05 entry touches 2024
        # That's: Dec 23-31 = 9 days
        self.assertEqual(result["total_days"], 9)

    def test_empty_timeoff_for_year_with_no_entries(self):
        """Should return zero values for year with no time off"""
        # Use a year with no data - year 2030 is unlikely to have test data
        result = calculate_timeoff_for_year(2030)
        self.assertEqual(result["total_days"], 0)
        self.assertEqual(result["total_weeks"], 0.0)
        self.assertEqual(result["total_workdays"], 0)
        self.assertEqual(len(result["entries"]), 0)

    def test_single_day_timeoff(self):
        """Should handle single-day time off correctly"""
        TimeOff.objects.create(
            title="Single Day",
            type="vacation",
            start_date=date(2025, 6, 15),
            end_date=date(2025, 6, 15),
        )

        result = calculate_timeoff_for_year(2025)
        # Should include the previous entries + 1
        self.assertIn(
            1, [e["period_days"] for e in result["entries"] if e["title"] == "Single Day"]
        )


class CalculateTimeoffForPeriodTestCase(TestCase):
    """Tests for calculate_timeoff_for_period function"""

    def setUp(self):
        """Create test TimeOff entries"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="timeoff_helpers-2",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Create timeoff entries for 2025
        self.winter_holiday = TimeOff.objects.create(
            title="Winter Holidays",
            type="vacation",
            start_date=date(2025, 2, 7),
            end_date=date(2025, 2, 14),
        )

        self.summer_holiday = TimeOff.objects.create(
            title="Summer Holidays",
            type="vacation",
            start_date=date(2025, 8, 9),
            end_date=date(2025, 8, 25),
        )

        # This crosses year boundary
        self.xmas_2025_2026 = TimeOff.objects.create(
            title="Christmas + New Year",
            type="holiday",
            start_date=date(2025, 12, 22),
            end_date=date(2026, 1, 5),
        )

    def test_period_within_single_month(self):
        """Calculate for a period entirely within one month"""
        result = calculate_timeoff_for_period(date(2025, 8, 1), date(2025, 8, 31))
        # Summer holiday: Aug 9-25 = 17 days, 11 weekdays (Mon–Fri exact)
        self.assertEqual(result["total_days"], 17)
        self.assertEqual(result["total_weeks"], 2.4)
        self.assertEqual(result["total_workdays"], 11)

    def test_period_spanning_multiple_months(self):
        """Calculate for a period spanning multiple months"""
        result = calculate_timeoff_for_period(date(2025, 2, 1), date(2025, 3, 31))
        # Winter holiday: Feb 7-14 = 8 days
        self.assertEqual(result["total_days"], 8)

    def test_period_with_no_timeoff(self):
        """Period with no time off entries"""
        result = calculate_timeoff_for_period(date(2025, 11, 1), date(2025, 11, 30))
        self.assertEqual(result["total_days"], 0)
        self.assertEqual(result["total_weeks"], 0.0)
        self.assertEqual(result["total_workdays"], 0)

    def test_period_partial_overlap_start(self):
        """Period overlaps only start of time off"""
        result = calculate_timeoff_for_period(date(2025, 8, 1), date(2025, 8, 15))
        # Summer holiday starts Aug 9, period ends Aug 15
        # Aug 9-15 = 7 days
        self.assertEqual(result["total_days"], 7)

    def test_period_partial_overlap_end(self):
        """Period overlaps only end of time off"""
        result = calculate_timeoff_for_period(date(2025, 8, 20), date(2025, 8, 31))
        # Summer holiday ends Aug 25, period starts Aug 20
        # Aug 20-25 = 6 days
        self.assertEqual(result["total_days"], 6)

    def test_period_crosses_year_boundary(self):
        """Period that crosses year boundary"""
        result = calculate_timeoff_for_period(date(2025, 12, 1), date(2025, 12, 31))
        # Christmas starts Dec 22, period ends Dec 31
        # Dec 22-31 = 10 days
        self.assertEqual(result["total_days"], 10)

    def test_period_includes_year_crossing_timeoff(self):
        """Period includes time off that crosses year boundary"""
        result = calculate_timeoff_for_period(date(2025, 12, 1), date(2026, 1, 31))
        # Christmas: Dec 22 - Jan 5 = 15 days total
        self.assertEqual(result["total_days"], 15)

    def test_period_full_year(self):
        """Calculate for full year should match year function"""
        from my_practice.utils.timeoff_helpers import calculate_timeoff_for_year

        result_period = calculate_timeoff_for_period(date(2025, 1, 1), date(2025, 12, 31))
        result_year = calculate_timeoff_for_year(2025)

        self.assertEqual(result_period["total_days"], result_year["total_days"])
        self.assertEqual(result_period["total_weeks"], result_year["total_weeks"])
        self.assertEqual(result_period["total_workdays"], result_year["total_workdays"])

    def test_quarter_period(self):
        """Calculate for Q4 2025"""
        result = calculate_timeoff_for_period(date(2025, 10, 1), date(2025, 12, 31))
        # Only Christmas in Q4: Dec 22-31 = 10 days
        self.assertEqual(result["total_days"], 10)
        self.assertEqual(result["total_weeks"], 1.4)

    def test_entries_detail(self):
        """Check that entries contain correct details"""
        result = calculate_timeoff_for_period(date(2025, 8, 10), date(2025, 8, 20))

        self.assertEqual(len(result["entries"]), 1)
        entry = result["entries"][0]

        self.assertEqual(entry["title"], "Summer Holidays")
        self.assertEqual(entry["period_start"], date(2025, 8, 10))
        self.assertEqual(entry["period_end"], date(2025, 8, 20))
        self.assertEqual(entry["period_days"], 11)  # Aug 10-20
