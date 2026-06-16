"""Tests for date helper utilities."""

from datetime import date

from django.test import TestCase
from my_practice.utils import DateRangeHelper


class TestDateRangeHelper(TestCase):
    """Test suite for DateRangeHelper class."""

    def test_get_year_range_from_date(self):
        """Test get_year_range returns correct tuple for given date."""
        test_date = date(2024, 6, 15)
        start, end = DateRangeHelper.get_year_range(test_date)

        self.assertEqual(start, date(2024, 1, 1))
        self.assertEqual(end, date(2024, 12, 31))

    def test_get_year_range_edge_cases(self):
        """Test get_year_range on first and last day of year."""
        # First day
        start, end = DateRangeHelper.get_year_range(date(2024, 1, 1))
        self.assertEqual(start, date(2024, 1, 1))
        self.assertEqual(end, date(2024, 12, 31))

        # Last day
        start, end = DateRangeHelper.get_year_range(date(2024, 12, 31))
        self.assertEqual(start, date(2024, 1, 1))
        self.assertEqual(end, date(2024, 12, 31))

    def test_get_month_range_regular_month(self):
        """Test get_month_range for regular 30-day month."""
        test_date = date(2024, 6, 15)
        start, end = DateRangeHelper.get_month_range(test_date)

        self.assertEqual(start, date(2024, 6, 1))
        self.assertEqual(end, date(2024, 6, 30))

    def test_get_month_range_31_day_month(self):
        """Test get_month_range for 31-day month."""
        test_date = date(2024, 1, 15)
        start, end = DateRangeHelper.get_month_range(test_date)

        self.assertEqual(start, date(2024, 1, 1))
        self.assertEqual(end, date(2024, 1, 31))

    def test_get_month_range_february_leap_year(self):
        """Test get_month_range for February in leap year."""
        test_date = date(2024, 2, 15)
        start, end = DateRangeHelper.get_month_range(test_date)

        self.assertEqual(start, date(2024, 2, 1))
        self.assertEqual(end, date(2024, 2, 29))

    def test_get_month_range_february_non_leap_year(self):
        """Test get_month_range for February in non-leap year."""
        test_date = date(2023, 2, 15)
        start, end = DateRangeHelper.get_month_range(test_date)

        self.assertEqual(start, date(2023, 2, 1))
        self.assertEqual(end, date(2023, 2, 28))

    def test_get_first_of_month(self):
        """Test get_first_of_month returns first day of month."""
        test_cases = [
            (date(2024, 6, 15), date(2024, 6, 1)),
            (date(2024, 1, 1), date(2024, 1, 1)),
            (date(2024, 12, 31), date(2024, 12, 1)),
        ]

        for input_date, expected in test_cases:
            result = DateRangeHelper.get_first_of_month(input_date)
            self.assertEqual(result, expected, f"Failed for {input_date}")

    def test_get_last_of_month(self):
        """Test get_last_of_month returns last day of month."""
        test_cases = [
            (date(2024, 6, 15), date(2024, 6, 30)),
            (date(2024, 1, 1), date(2024, 1, 31)),
            (date(2024, 2, 10), date(2024, 2, 29)),  # Leap year
            (date(2023, 2, 10), date(2023, 2, 28)),  # Non-leap year
        ]

        for input_date, expected in test_cases:
            result = DateRangeHelper.get_last_of_month(input_date)
            self.assertEqual(result, expected, f"Failed for {input_date}")

    def test_add_months_positive(self):
        """Test add_months with positive month offset."""
        start_date = date(2024, 1, 15)

        # Add 1 month
        result = DateRangeHelper.add_months(start_date, 1)
        self.assertEqual(result, date(2024, 2, 15))

        # Add 6 months
        result = DateRangeHelper.add_months(start_date, 6)
        self.assertEqual(result, date(2024, 7, 15))

        # Add 12 months (cross year)
        result = DateRangeHelper.add_months(start_date, 12)
        self.assertEqual(result, date(2025, 1, 15))

    def test_add_months_negative(self):
        """Test add_months with negative month offset."""
        start_date = date(2024, 6, 15)

        # Subtract 1 month
        result = DateRangeHelper.add_months(start_date, -1)
        self.assertEqual(result, date(2024, 5, 15))

        # Subtract 6 months
        result = DateRangeHelper.add_months(start_date, -6)
        self.assertEqual(result, date(2023, 12, 15))

    def test_add_months_edge_case_end_of_month(self):
        """Test add_months handles end-of-month edge cases."""
        # January 31 + 1 month = February 29 (leap year)
        result = DateRangeHelper.add_months(date(2024, 1, 31), 1)
        self.assertEqual(result, date(2024, 2, 29))

        # January 31 + 1 month = February 28 (non-leap year)
        result = DateRangeHelper.add_months(date(2023, 1, 31), 1)
        self.assertEqual(result, date(2023, 2, 28))

    def test_add_years_positive(self):
        """Test add_years with positive year offset."""
        start_date = date(2024, 6, 15)

        # Add 1 year
        result = DateRangeHelper.add_years(start_date, 1)
        self.assertEqual(result, date(2025, 6, 15))

        # Add 5 years
        result = DateRangeHelper.add_years(start_date, 5)
        self.assertEqual(result, date(2029, 6, 15))

    def test_add_years_negative(self):
        """Test add_years with negative year offset."""
        start_date = date(2024, 6, 15)

        # Subtract 1 year
        result = DateRangeHelper.add_years(start_date, -1)
        self.assertEqual(result, date(2023, 6, 15))

    def test_add_years_leap_year_edge_case(self):
        """Test add_years handles leap year edge case."""
        # February 29, 2024 + 1 year = February 28, 2025 (not a leap year)
        result = DateRangeHelper.add_years(date(2024, 2, 29), 1)
        self.assertEqual(result, date(2025, 2, 28))

    def test_months_between_same_year(self):
        """Test months_between for dates in same year."""
        start = date(2024, 3, 15)
        end = date(2024, 8, 20)

        result = DateRangeHelper.months_between(start, end)
        self.assertEqual(result, 5)

    def test_months_between_cross_year(self):
        """Test months_between for dates crossing year boundary."""
        start = date(2023, 10, 15)
        end = date(2024, 3, 20)

        result = DateRangeHelper.months_between(start, end)
        self.assertEqual(result, 5)

    def test_months_between_same_month(self):
        """Test months_between for dates in same month."""
        start = date(2024, 6, 1)
        end = date(2024, 6, 30)

        result = DateRangeHelper.months_between(start, end)
        self.assertEqual(result, 0)

    def test_months_between_exact_years(self):
        """Test months_between for exactly 12 months."""
        start = date(2023, 6, 15)
        end = date(2024, 6, 15)

        result = DateRangeHelper.months_between(start, end)
        self.assertEqual(result, 12)

    def test_generate_month_range_same_year(self):
        """Test generate_month_range within same year."""
        start = date(2024, 3, 15)
        end = date(2024, 6, 20)

        result = DateRangeHelper.generate_month_range(start, end)

        expected = [
            date(2024, 3, 1),
            date(2024, 4, 1),
            date(2024, 5, 1),
            date(2024, 6, 1),
        ]
        self.assertEqual(result, expected)

    def test_generate_month_range_cross_year(self):
        """Test generate_month_range crossing year boundary."""
        start = date(2023, 11, 15)
        end = date(2024, 2, 20)

        result = DateRangeHelper.generate_month_range(start, end)

        expected = [
            date(2023, 11, 1),
            date(2023, 12, 1),
            date(2024, 1, 1),
            date(2024, 2, 1),
        ]
        self.assertEqual(result, expected)

    def test_generate_month_range_same_month(self):
        """Test generate_month_range for dates in same month."""
        start = date(2024, 6, 1)
        end = date(2024, 6, 30)

        result = DateRangeHelper.generate_month_range(start, end)

        expected = [date(2024, 6, 1)]
        self.assertEqual(result, expected)

    def test_format_month_year_long(self):
        """Test format_month_year with long format."""
        test_date = date(2024, 6, 15)

        result = DateRangeHelper.format_month_year(test_date, short=False)

        # Depends on locale, but should contain month name and year
        self.assertIn("2024", result)
        # Should be longer format (e.g., "June 2024" or "Juni 2024")

    def test_format_month_year_short(self):
        """Test format_month_year with short format."""
        test_date = date(2024, 6, 15)

        result = DateRangeHelper.format_month_year(test_date, short=True)

        # Should be short format (e.g., "Jun 24")
        self.assertIn("Jun", result)
        self.assertIn("24", result)

    def test_count_working_days_single_week(self):
        """Test count_working_days for a single week."""
        # Monday to Friday (5 working days)
        start = date(2025, 11, 17)  # Monday
        end = date(2025, 11, 21)  # Friday

        result = DateRangeHelper.count_working_days(start, end)
        self.assertEqual(result, 5)

    def test_count_working_days_with_weekend(self):
        """Test count_working_days spanning a weekend."""
        # Friday to Monday (2 working days: Fri + Mon)
        start = date(2025, 11, 14)  # Friday
        end = date(2025, 11, 17)  # Monday

        result = DateRangeHelper.count_working_days(start, end)
        self.assertEqual(result, 2)

    def test_count_working_days_weekend_only(self):
        """Test count_working_days for weekend days only."""
        # Saturday to Sunday (0 working days)
        start = date(2025, 11, 15)  # Saturday
        end = date(2025, 11, 16)  # Sunday

        result = DateRangeHelper.count_working_days(start, end)
        self.assertEqual(result, 0)

    def test_count_working_days_single_day_weekday(self):
        """Test count_working_days for single weekday."""
        # Single Monday
        start = date(2025, 11, 17)  # Monday
        end = date(2025, 11, 17)  # Same Monday

        result = DateRangeHelper.count_working_days(start, end)
        self.assertEqual(result, 1)

    def test_count_working_days_single_day_weekend(self):
        """Test count_working_days for single weekend day."""
        # Single Saturday
        start = date(2025, 11, 15)  # Saturday
        end = date(2025, 11, 15)  # Same Saturday

        result = DateRangeHelper.count_working_days(start, end)
        self.assertEqual(result, 0)

    def test_count_working_days_full_month(self):
        """Test count_working_days for full month."""
        # November 2025: 30 days total, 21 working days (Mon-Fri)
        start = date(2025, 11, 1)
        end = date(2025, 11, 30)

        result = DateRangeHelper.count_working_days(start, end)
        self.assertEqual(result, 20)  # Nov 2025 has 20 weekdays

    def test_count_working_days_with_holidays_span(self):
        """Test count_working_days for end-of-year period."""
        # Dec 23-31, 2025: 9 total days, 7 working days
        start = date(2025, 12, 23)  # Tuesday
        end = date(2025, 12, 31)  # Wednesday

        result = DateRangeHelper.count_working_days(start, end)
        self.assertEqual(result, 7)  # Tue-Fri + Mon-Wed

    # Note: The following methods are not yet implemented in DateRangeHelper
    # They can be added in the future if needed:
    # - is_same_month()
    # - is_same_year()
    # - get_quarter_range()
    # - datetime_to_date()
