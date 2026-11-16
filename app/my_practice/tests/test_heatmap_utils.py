"""The month window of ``get_heatmap_data``: which months, oldest first, across a year end."""

from datetime import date

from django.test import TestCase

from ..utils.heatmap_utils import get_heatmap_data


class HeatmapMonthWindowTests(TestCase):
    def _months(self, **kwargs) -> list[date]:
        result = get_heatmap_data(practice=None, **kwargs)
        return [row["month_date"] for row in result["heatmap_data"]]

    def test_months_run_oldest_first_across_a_year_end(self):
        self.assertEqual(
            self._months(current_year=2026, current_month=2, months_to_show=4),
            [date(2025, 11, 1), date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)],
        )

    def test_start_offset_moves_the_window_back(self):
        self.assertEqual(
            self._months(current_year=2026, current_month=2, months_to_show=2, start_offset=3),
            [date(2025, 10, 1), date(2025, 11, 1)],
        )

    def test_negative_offset_reaches_into_the_future(self):
        self.assertEqual(
            self._months(current_year=2025, current_month=11, months_to_show=2, start_offset=-2),
            [date(2025, 12, 1), date(2026, 1, 1)],
        )

    def test_range_covers_the_first_to_the_last_day_shown(self):
        result = get_heatmap_data(2026, 3, months_to_show=3, start_offset=1, practice=None)
        self.assertEqual(result["range_start_date"], date(2025, 12, 1))
        self.assertEqual(result["range_end_date_full"], date(2026, 2, 28))
