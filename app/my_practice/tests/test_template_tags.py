"""
Tests for payment template tags.
"""

from datetime import date

from django.template import Context, Template
from django.test import RequestFactory, TestCase
from my_practice.models import Practice
from my_practice.templatetags.payment_tags import (
    abs_value,
    currency,
    format_month_year,
    highlight_diff,
    hours,
    percent,
    percentage,
)


class CurrencyFilterTests(TestCase):
    """Tests for the currency template filter."""

    def test_currency_basic(self):
        """Test basic currency formatting (German format)."""
        self.assertEqual(currency(1234.56), "1.234,56\u00a0€")

    def test_currency_with_custom_symbol(self):
        """Test currency with custom symbol."""
        self.assertEqual(currency(1234.56, "$"), "1.234,56\u00a0$")

    def test_currency_with_none(self):
        """Test currency with None value."""
        self.assertEqual(currency(None), "–")

    def test_currency_with_zero(self):
        """Test currency with zero value."""
        self.assertEqual(currency(0), "0,00\u00a0€")

    def test_currency_large_number(self):
        """Test currency with large number."""
        self.assertEqual(currency(1234567.89), "1.234.567,89\u00a0€")

    def test_currency_negative_number(self):
        """Test currency with negative number."""
        self.assertEqual(currency(-100.50), "-100,50\u00a0€")

    def test_currency_very_small_number(self):
        """Test currency with very small number."""
        self.assertEqual(currency(0.01), "0,01\u00a0€")

    def test_currency_string_coercion(self):
        """Test currency with string input."""
        self.assertEqual(currency("99.99"), "99,99\u00a0€")


class PercentFilterTests(TestCase):
    """Tests for the percent template filter."""

    def test_percent_basic(self):
        """Test basic percent formatting."""
        self.assertEqual(percent(45.6), "45.6%")

    def test_percent_with_decimals(self):
        """Test percent with custom decimals."""
        self.assertEqual(percent(45.678, 2), "45.68%")

    def test_percent_with_none(self):
        """Test percent with None value."""
        self.assertEqual(percent(None), "–")

    def test_percent_with_zero(self):
        """Test percent with zero value."""
        self.assertEqual(percent(0), "0.0%")

    def test_percent_negative(self):
        """Test percent with negative value."""
        self.assertEqual(percent(-25.5), "-25.5%")

    def test_percent_very_large(self):
        """Test percent with very large value."""
        self.assertEqual(percent(12345.67), "12345.7%")

    def test_percent_rounding(self):
        """Test percent rounds correctly."""
        self.assertEqual(percent(45.666, 1), "45.7%")
        self.assertEqual(percent(45.654, 2), "45.65%")


class PercentageFilterTests(TestCase):
    """Tests for the percentage template filter (calculates part/total)."""

    def test_percentage_basic(self):
        """Test basic percentage calculation."""
        self.assertEqual(percentage(25, 100), "25.0%")

    def test_percentage_decimal(self):
        """Test percentage with decimal result."""
        self.assertEqual(percentage(33.33, 100), "33.3%")

    def test_percentage_over_hundred(self):
        """Test percentage over 100%."""
        self.assertEqual(percentage(150, 100), "150.0%")

    def test_percentage_zero_total(self):
        """Test percentage with zero total."""
        self.assertEqual(percentage(10, 0), "0%")

    def test_percentage_with_none(self):
        """Test percentage with None values."""
        self.assertEqual(percentage(None, 100), "–")
        self.assertEqual(percentage(50, None), "–")

    def test_percentage_both_zero(self):
        """Test percentage when both are zero."""
        self.assertEqual(percentage(0, 0), "0%")

    def test_percentage_negative_part(self):
        """Test percentage with negative part."""
        self.assertEqual(percentage(-25, 100), "-25.0%")

    def test_percentage_fractional(self):
        """Test percentage with fractional values."""
        self.assertEqual(percentage(12.5, 50), "25.0%")


class HoursFilterTests(TestCase):
    """Tests for the hours template filter."""

    def test_hours_basic(self):
        """Test basic hours formatting."""
        self.assertEqual(hours(5.5), "5.5h")

    def test_hours_with_none(self):
        """Test hours with None value."""
        self.assertEqual(hours(None), "–")

    def test_hours_with_zero(self):
        """Test hours with zero value."""
        self.assertEqual(hours(0), "0.0h")

    def test_hours_integer(self):
        """Test hours with integer value."""
        self.assertEqual(hours(8), "8.0h")

    def test_hours_fractional(self):
        """Test hours with fractional value."""
        self.assertEqual(hours(2.75), "2.8h")  # rounds to 1 decimal

    def test_hours_large_number(self):
        """Test hours with large number."""
        self.assertEqual(hours(168.5), "168.5h")  # full week


class HighlightDiffFilterTests(TestCase):
    """Tests for the highlight_diff template filter."""

    def test_highlight_diff_positive(self):
        """Test highlight_diff with positive value."""
        self.assertEqual(highlight_diff(10), "text-success")

    def test_highlight_diff_negative(self):
        """Test highlight_diff with negative value."""
        self.assertEqual(highlight_diff(-10), "text-danger")

    def test_highlight_diff_zero(self):
        """Test highlight_diff with zero value."""
        self.assertEqual(highlight_diff(0), "")

    def test_highlight_diff_with_threshold(self):
        """Test highlight_diff with custom threshold."""
        self.assertEqual(highlight_diff(5, 10), "text-danger")
        self.assertEqual(highlight_diff(15, 10), "text-success")


class AbsValueFilterTests(TestCase):
    """Tests for the abs_value template filter."""

    def test_abs_value_positive(self):
        """Test abs_value with positive number."""
        self.assertEqual(abs_value(10), 10)

    def test_abs_value_negative(self):
        """Test abs_value with negative number."""
        self.assertEqual(abs_value(-10), 10)

    def test_abs_value_zero(self):
        """Test abs_value with zero."""
        self.assertEqual(abs_value(0), 0)

    def test_abs_value_decimal(self):
        """Test abs_value with decimal."""
        self.assertEqual(abs_value(-99.99), 99.99)

    def test_abs_value_none(self):
        """Test abs_value with None returns None."""
        self.assertIsNone(abs_value(None))


class QueryStringTemplateTagTests(TestCase):
    """Test cases for the query_string template tag."""

    def setUp(self):
        """Set up test request factory."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="template_tags-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.factory = RequestFactory()

    def test_query_string_preserves_params(self):
        """Test that query_string preserves existing parameters."""
        request = self.factory.get("/test/?status=paid&year=2025")
        template = Template("{% load payment_tags %}{% query_string page=2 %}")
        context = Context({"request": request})
        result = template.render(context)

        self.assertIn("status=paid", result)
        self.assertIn("year=2025", result)
        self.assertIn("page=2", result)

    def test_query_string_updates_param(self):
        """Test that query_string updates existing parameter."""
        request = self.factory.get("/test/?page=1&status=paid")
        template = Template("{% load payment_tags %}{% query_string page=2 %}")
        context = Context({"request": request})
        result = template.render(context)

        self.assertIn("page=2", result)
        self.assertNotIn("page=1", result)
        self.assertIn("status=paid", result)

    def test_query_string_removes_param(self):
        """Test that query_string removes parameter with empty value."""
        request = self.factory.get("/test/?page=1&status=paid")
        template = Template("{% load payment_tags %}{% query_string status='' %}")
        context = Context({"request": request})
        result = template.render(context)

        self.assertNotIn("status", result)
        self.assertIn("page=1", result)

    def test_query_string_no_params(self):
        """Test query_string with no existing parameters."""
        request = self.factory.get("/test/")
        template = Template("{% load payment_tags %}{% query_string page=2 %}")
        context = Context({"request": request})
        result = template.render(context)

        # Django escapes & to &amp; in templates
        self.assertIn("page=2", result)

    def test_query_string_multiple_params(self):
        """Test query_string with multiple new parameters."""
        request = self.factory.get("/test/")
        template = Template("{% load payment_tags %}{% query_string page=2 status='paid' %}")
        context = Context({"request": request})
        result = template.render(context)

        self.assertIn("page=2", result)
        self.assertIn("status=paid", result)

    def test_query_string_no_request(self):
        """Test query_string when no request in context."""
        template = Template("{% load payment_tags %}{% query_string page=2 %}")
        context = Context({})
        result = template.render(context)

        self.assertEqual(result.strip(), "")


class FormatMonthYearFilterTests(TestCase):
    """Tests for the format_month_year template filter."""

    def test_format_month_year_basic(self):
        """Test basic month/year formatting in German."""
        test_date = date(2025, 1, 15)
        self.assertEqual(format_month_year(test_date), "Jan 2025")

    def test_format_month_year_december(self):
        """Test December formatting."""
        test_date = date(2024, 12, 31)
        self.assertEqual(format_month_year(test_date), "Dez 2024")

    def test_format_month_year_march(self):
        """Test March formatting (German: Mär)."""
        test_date = date(2023, 3, 15)
        self.assertEqual(format_month_year(test_date), "Mär 2023")

    def test_format_month_year_october(self):
        """Test October formatting (German: Okt)."""
        test_date = date(2022, 10, 1)
        self.assertEqual(format_month_year(test_date), "Okt 2022")

    def test_format_month_year_with_none(self):
        """Test format_month_year with None value."""
        self.assertEqual(format_month_year(None), "–")

    def test_format_month_year_all_months(self):
        """Test all months are correctly mapped."""
        expected = [
            "Jan",
            "Feb",
            "Mär",
            "Apr",
            "Mai",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Okt",
            "Nov",
            "Dez",
        ]
        for month, month_name in enumerate(expected, 1):
            test_date = date(2025, month, 1)
            self.assertEqual(
                format_month_year(test_date),
                f"{month_name} 2025",
                f"Failed for month {month}",
            )
