"""
Tests for PracticeDayCalculator (P-027 Fahrtkosten).
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from my_practice.models import Client, Practice, Session
from my_practice.utils.practice_days import (
    HOME_OFFICE_MAX_DAYS,
    HomeOfficeDayCalculator,
    PracticeDayCalculator,
    berlin_public_holidays,
)


class BerlinPublicHolidaysTestCase(TestCase):
    """Test Berlin public holiday computation."""

    def test_2025_count(self):
        """2025 has 13 Berlin public holidays (incl. Frauentag + Reformationstag)."""
        holidays = berlin_public_holidays(2025)
        self.assertEqual(len(holidays), 13)

    def test_fixed_holidays_2025(self):
        holidays = berlin_public_holidays(2025)
        self.assertIn(date(2025, 1, 1), holidays)  # Neujahr
        self.assertIn(date(2025, 5, 1), holidays)  # Tag der Arbeit
        self.assertIn(date(2025, 10, 3), holidays)  # Tag der Deutschen Einheit
        self.assertIn(date(2025, 10, 31), holidays)  # Reformationstag (seit 2018)
        self.assertIn(date(2025, 3, 8), holidays)  # Frauentag (seit 2019)
        self.assertIn(date(2025, 12, 25), holidays)  # 1. Weihnachtstag
        self.assertIn(date(2025, 12, 26), holidays)  # 2. Weihnachtstag

    def test_easter_2025(self):
        holidays = berlin_public_holidays(2025)
        self.assertIn(date(2025, 4, 18), holidays)  # Karfreitag
        self.assertIn(date(2025, 4, 21), holidays)  # Ostermontag
        self.assertIn(date(2025, 5, 29), holidays)  # Christi Himmelfahrt
        self.assertIn(date(2025, 6, 9), holidays)  # Pfingstmontag

    def test_reformationstag_not_before_2018(self):
        holidays_2017 = berlin_public_holidays(2017)
        self.assertNotIn(date(2017, 10, 31), holidays_2017)

    def test_frauentag_not_before_2019(self):
        holidays_2018 = berlin_public_holidays(2018)
        self.assertNotIn(date(2018, 3, 8), holidays_2018)


class PracticeDayCalculatorTestCase(TestCase):
    """Test PracticeDayCalculator with a mock Practice object."""

    def _make_practice(self, distance_km=None, weekdays=None):
        """Create a simple mock practice without DB access."""

        class MockPractice:
            commute_distance_km = distance_km
            practice_weekdays = weekdays if weekdays is not None else []

        return MockPractice()

    def test_not_configured_returns_zeros(self):
        practice = self._make_practice(distance_km=None, weekdays=[])
        result = PracticeDayCalculator(practice, 2025).calculate()
        self.assertEqual(result.practice_days, 0)
        self.assertEqual(result.session_days, 0)
        self.assertEqual(result.deduction_total, Decimal("0"))
        self.assertFalse(result.is_configured)

    def test_no_distance_returns_zeros(self):
        practice = self._make_practice(distance_km=0, weekdays=[0, 1, 2, 3, 4])
        result = PracticeDayCalculator(practice, 2025).calculate()
        self.assertFalse(result.is_configured)
        self.assertEqual(result.deduction_total, Decimal("0"))

    def test_practice_days_monday_only_2025(self):
        """2025 has 52 Mondays; minus Mon public holidays."""
        practice = self._make_practice(distance_km=10, weekdays=[0])  # Mondays only
        result = PracticeDayCalculator(practice, 2025).calculate()
        # 52 Mondays in 2025; none are Berlin public holidays on a Monday in 2025
        # (Karfreitag=Fri, Ostermontag=Mon Apr 21 ✓, Tag der Arbeit=Thu, etc.)
        # Ostermontag 2025 = April 21 = Monday → excluded
        # Pfingstmontag 2025 = June 9 = Monday → excluded
        self.assertGreater(result.total_possible_days, 50)
        self.assertLess(result.practice_days, result.total_possible_days)

    def test_deduction_under_20km(self):
        """Without sessions in DB, session_days=0 so deduction=0."""
        practice = self._make_practice(distance_km=10, weekdays=[0, 1, 2, 3, 4])
        result = PracticeDayCalculator(practice, 2025).calculate()
        self.assertEqual(result.session_days, 0)
        self.assertEqual(result.deduction_total, Decimal("0"))
        self.assertEqual(result.deduction_above_20_km, Decimal("0"))
        # Calendar-based days are still computed
        self.assertGreater(result.practice_days, 0)

    def test_deduction_exactly_20km(self):
        """Without sessions, deduction_total=0 regardless of km."""
        practice = self._make_practice(distance_km=20, weekdays=[0])
        result = PracticeDayCalculator(practice, 2025).calculate()
        self.assertEqual(result.deduction_above_20_km, Decimal("0"))
        self.assertEqual(result.deduction_total, Decimal("0"))
        self.assertGreater(result.practice_days, 0)

    def test_deduction_above_20km(self):
        """Without sessions, all deduction components are 0."""
        practice = self._make_practice(distance_km=25, weekdays=[0])
        result = PracticeDayCalculator(practice, 2025).calculate()
        self.assertEqual(result.deduction_first_20_km, Decimal("0"))
        self.assertEqual(result.deduction_above_20_km, Decimal("0"))
        self.assertEqual(result.deduction_total, Decimal("0"))
        self.assertGreater(result.practice_days, 0)

    def test_leap_year_2024(self):
        """Leap year: 2024 has 366 days, should not cause errors."""
        practice = self._make_practice(distance_km=12, weekdays=[0, 1, 2, 3, 4])
        result = PracticeDayCalculator(practice, 2024).calculate()
        self.assertGreater(result.practice_days, 240)
        self.assertLess(result.practice_days, 265)

    def test_weekdays_list_respected(self):
        """Half the week (Mon+Tue only) should give roughly half the days."""
        practice_full = self._make_practice(distance_km=10, weekdays=[0, 1, 2, 3, 4])
        practice_half = self._make_practice(distance_km=10, weekdays=[0, 1])
        result_full = PracticeDayCalculator(practice_full, 2025).calculate()
        result_half = PracticeDayCalculator(practice_half, 2025).calculate()
        # 2 out of 5 days ≈ 40%; allow ±10%
        ratio = result_half.practice_days / result_full.practice_days
        self.assertAlmostEqual(ratio, 0.4, delta=0.1)

    def test_is_configured_true(self):
        practice = self._make_practice(distance_km=15, weekdays=[0, 1, 2])
        result = PracticeDayCalculator(practice, 2025).calculate()
        self.assertTrue(result.is_configured)


class PracticeDayCalculatorSessionTestCase(TestCase):
    """Test deduction calculations against actual Session objects in the DB."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Praxis",
            slug="test-praxis-fahrtkosten",
            title="Test",
            email="test@example.com",
            city="Berlin",
        )
        self.client_obj = Client.objects.create(
            client_code="FK-1",
            full_name="Max Mustermann",
            practice=self.practice,
        )

    def _make_practice(self, distance_km, weekdays):
        self.practice.commute_distance_km = distance_km
        self.practice.practice_weekdays = weekdays
        return self.practice

    def _add_sessions(self, dates):
        for d in dates:
            Session.objects.get_or_create(client=self.client_obj, session_date=d)

    def test_deduction_under_20km_with_sessions(self):
        """10 km: only first-bracket rate, based on session days."""
        self._add_sessions([date(2025, 1, 6), date(2025, 1, 13), date(2025, 1, 20)])
        practice = self._make_practice(distance_km=10, weekdays=[0, 1, 2, 3, 4])
        result = PracticeDayCalculator(practice, 2025).calculate()
        self.assertEqual(result.session_days, 3)
        expected = Decimal("10") * Decimal("0.30") * 3
        self.assertEqual(result.deduction_total, expected)
        self.assertEqual(result.deduction_above_20_km, Decimal("0"))

    def test_deduction_above_20km_with_sessions(self):
        """25 km: 20 km at 0.30 + 5 km at 0.38, 3 sessions."""
        self._add_sessions([date(2025, 3, 3), date(2025, 3, 10), date(2025, 3, 17)])
        practice = self._make_practice(distance_km=25, weekdays=[0])
        result = PracticeDayCalculator(practice, 2025).calculate()
        self.assertEqual(result.session_days, 3)
        expected_first = Decimal("20") * Decimal("0.30") * 3
        expected_above = Decimal("5") * Decimal("0.38") * 3
        self.assertEqual(result.deduction_first_20_km, expected_first)
        self.assertEqual(result.deduction_above_20_km, expected_above)
        self.assertEqual(result.deduction_total, expected_first + expected_above)

    def test_session_on_holiday_counts(self):
        """Session on a public holiday still counts — the drive was real (§9 EStG)."""
        self._add_sessions([date(2025, 4, 21)])  # Ostermontag (Monday)
        practice = self._make_practice(distance_km=10, weekdays=[0])
        result = PracticeDayCalculator(practice, 2025).calculate()
        self.assertEqual(result.session_days, 1)

    def test_session_on_wrong_weekday_excluded(self):
        """Session on Saturday is excluded even if it exists in DB."""
        self._add_sessions([date(2025, 1, 4)])  # Saturday
        practice = self._make_practice(distance_km=10, weekdays=[0, 1, 2, 3, 4])
        result = PracticeDayCalculator(practice, 2025).calculate()
        self.assertEqual(result.session_days, 0)


class HomeOfficeDayCalculatorTestCase(TestCase):
    """Test HomeOfficeDayCalculator for calendar-based pauschale calculation."""

    def _make_practice(self, weekdays=None):
        class MockPractice:
            practice_weekdays = weekdays if weekdays is not None else []

        return MockPractice()

    def test_not_configured_returns_zeros(self):
        practice = self._make_practice(weekdays=[])
        result = HomeOfficeDayCalculator(practice, 2025).calculate()
        self.assertFalse(result.is_configured)
        self.assertEqual(result.home_office_days, 0)
        self.assertEqual(result.deduction_total, Decimal("0"))

    def test_home_office_weekdays_are_complement(self):
        practice = self._make_practice(weekdays=[0, 2, 4])
        result = HomeOfficeDayCalculator(practice, 2025).calculate()
        self.assertTrue(result.is_configured)
        self.assertEqual(result.home_office_weekdays, [1, 3])
        self.assertGreater(result.home_office_days, 0)

    def test_deduction_is_capped(self):
        # Only Friday is a practice day; home-office can still exceed annual cap.
        practice = self._make_practice(weekdays=[4])
        result = HomeOfficeDayCalculator(practice, 2025).calculate()
        self.assertLessEqual(result.capped_days, HOME_OFFICE_MAX_DAYS)
        self.assertEqual(result.deduction_total, Decimal(str(result.capped_days * 6)))
