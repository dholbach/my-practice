"""Tests for capacity calculation helpers."""

from datetime import date

from django.test import TestCase
from my_practice.models import CapacityPeriod, Practice, TimeOff
from my_practice.utils.capacity_helpers import (
    _calculate_weighted_capacity,
    calculate_period_capacity,
    get_weekly_capacity_for_date,
)


def _make_capacity_periods():
    """Create a Practice and the two standard capacity periods used across all tests.

    Period 1: 10 h/week from 2015-01-01 (covers all pre-2023-08-01 dates)
    Period 2: 20 h/week from 2023-08-01 (covers all post-2023-07-31 dates)
    """
    practice = Practice.objects.create(name="Cap Test", slug="cap-test-helper", email="c@t.com")
    CapacityPeriod.objects.create(practice=practice, start_date=date(2015, 1, 1), hours_per_week=10)
    CapacityPeriod.objects.create(practice=practice, start_date=date(2023, 8, 1), hours_per_week=20)
    return practice


class GetWeeklyCapacityTests(TestCase):
    """Test capacity period lookup boundaries."""

    @classmethod
    def setUpTestData(cls):
        _make_capacity_periods()

    def test_before_first_period_uses_first_config(self):
        self.assertEqual(get_weekly_capacity_for_date(date(2019, 6, 1)), 10)

    def test_building_phase(self):
        self.assertEqual(get_weekly_capacity_for_date(date(2022, 3, 15)), 10)

    def test_day_before_capacity_change(self):
        self.assertEqual(get_weekly_capacity_for_date(date(2023, 7, 31)), 10)

    def test_day_of_capacity_change(self):
        self.assertEqual(get_weekly_capacity_for_date(date(2023, 8, 1)), 20)

    def test_after_capacity_change(self):
        self.assertEqual(get_weekly_capacity_for_date(date(2026, 1, 1)), 20)


class WeightedCapacityTests(TestCase):
    """Test _calculate_weighted_capacity, especially periods spanning a capacity change.

    July 2023 has 21 weekdays (10h/week config), August 2023 has 23 weekdays
    (20h/week config); no Berlin public holidays fall in either month.
    """

    @classmethod
    def setUpTestData(cls):
        _make_capacity_periods()

    START = date(2023, 7, 1)
    END = date(2023, 8, 31)
    JULY_DAYS = 21
    AUG_DAYS = 23

    def test_single_config_period(self):
        """A period without a capacity change: available_days / 5 * hours_per_week."""
        # June 2026, 22 working days assumed by caller
        result = _calculate_weighted_capacity(date(2026, 6, 1), date(2026, 6, 30), 22)
        self.assertAlmostEqual(result, 22 / 5 * 20)

    def test_spanning_period_without_timeoff(self):
        """Spanning the 2023-08-01 change weights each config by its working days."""
        total_days = self.JULY_DAYS + self.AUG_DAYS
        result = _calculate_weighted_capacity(self.START, self.END, total_days)
        expected = (self.JULY_DAYS * 10 + self.AUG_DAYS * 20) / 5
        self.assertAlmostEqual(result, expected)

    def test_spanning_period_respects_timeoff(self):
        """Regression: time off must reduce capacity even when the period spans
        a capacity change (available_working_days was previously ignored)."""
        total_days = self.JULY_DAYS + self.AUG_DAYS
        full = _calculate_weighted_capacity(self.START, self.END, total_days)
        reduced = _calculate_weighted_capacity(self.START, self.END, total_days - 10)

        self.assertLess(reduced, full)
        # Reduction is proportional to lost working days
        self.assertAlmostEqual(reduced, full * (total_days - 10) / total_days)

    def test_zero_available_days(self):
        result = _calculate_weighted_capacity(self.START, self.END, 0)
        self.assertEqual(result, 0.0)


class PeriodCapacityWithTimeoffTests(TestCase):
    """Integration test: calculate_period_capacity subtracts time off for
    periods spanning a capacity change."""

    @classmethod
    def setUpTestData(cls):
        _make_capacity_periods()

    def test_timeoff_reduces_capacity_across_capacity_change(self):
        start, end = date(2023, 7, 1), date(2023, 8, 31)

        without = calculate_period_capacity(start, end, include_timeoff=False)

        # Two vacation weeks straddling the capacity change (Jul 24 – Aug 4)
        TimeOff.objects.create(
            title="Sommerurlaub",
            type="vacation",
            start_date=date(2023, 7, 24),
            end_date=date(2023, 8, 4),
        )
        with_timeoff = calculate_period_capacity(start, end, include_timeoff=True)

        self.assertEqual(without["working_days_total"], 44)
        self.assertEqual(with_timeoff["timeoff_days"], 10)
        self.assertEqual(with_timeoff["working_days_available"], 34)
        self.assertLess(with_timeoff["usable_capacity_hours"], without["usable_capacity_hours"])
        # Weighted hours/week: (21*10 + 23*20) / 44; applied to 34 available days
        expected = 34 / 5 * ((21 * 10 + 23 * 20) / 44)
        self.assertAlmostEqual(with_timeoff["usable_capacity_hours"], expected)
