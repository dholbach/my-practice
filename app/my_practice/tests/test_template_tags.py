"""
Tests for payment template tags.
"""

from datetime import date

from django.template import Context, Template
from django.test import RequestFactory, TestCase

from my_practice.models import Practice
from my_practice.templatetags.payment_tags import (
    currency,
    doc_field,
    format_hours,
    format_month_year,
    highlight_diff,
    hours,
    percentage,
    privacy_name,
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


class FormatHoursFilterTests(TestCase):
    """Tests for the format_hours filter (heatmap labels)."""

    def test_whole_numbers_drop_the_decimal(self):
        self.assertEqual(format_hours(8), "8")
        self.assertEqual(format_hours(2.0), "2")

    def test_fractions_keep_one_decimal(self):
        self.assertEqual(format_hours(2.75), "2.8")
        self.assertEqual(format_hours(0.5), "0.5")

    def test_non_numbers_pass_through(self):
        self.assertEqual(format_hours("n/a"), "n/a")
        self.assertIsNone(format_hours(None))


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


class PrivacyNameFilterTests(TestCase):
    """The initials-visible treatment: used where a blurred name would leave
    nothing to identify the record by — inquiries have no client code, and a
    picker's rows have to be told apart (M-PAT-08)."""

    def test_initial_stays_legible_and_remainder_is_blurred(self):
        self.assertEqual(
            privacy_name("Max Mustermann"),
            'M<span class="sensitive-data pn-rest">ax</span> '
            'M<span class="sensitive-data pn-rest">ustermann</span>',
        )

    def test_single_letter_word_has_nothing_left_to_blur(self):
        self.assertEqual(
            privacy_name("A Schmidt"), 'A S<span class="sensitive-data pn-rest">chmidt</span>'
        )

    def test_empty_value_renders_nothing(self):
        self.assertEqual(privacy_name(""), "")
        self.assertEqual(privacy_name(None), "")

    def test_html_in_a_name_is_escaped(self):
        """Output is mark_safe'd, so the filter has to escape it itself."""
        rendered = privacy_name("<script>alert(1)</script> Schmidt")
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;", rendered)

    def test_rendered_through_a_template_is_not_double_escaped(self):
        template = Template("{% load payment_tags %}{{ name|privacy_name }}")
        rendered = template.render(Context({"name": "Anna Schmidt"}))
        self.assertIn('A<span class="sensitive-data pn-rest">nna</span>', rendered)


class DocFieldTagTests(TestCase):
    """doc_field reads the _de or _en field of a document's language."""

    def setUp(self):
        self.practice = Practice(subtitle_de="Untertitel", subtitle_en="Subtitle")

    def test_english_reads_the_en_field(self):
        self.assertEqual(doc_field(self.practice, "subtitle", "en"), "Subtitle")

    def test_german_reads_the_de_field(self):
        self.assertEqual(doc_field(self.practice, "subtitle", "de"), "Untertitel")

    def test_any_other_language_falls_back_to_german(self):
        self.assertEqual(doc_field(self.practice, "subtitle", ""), "Untertitel")
        self.assertEqual(doc_field(self.practice, "subtitle", "fr"), "Untertitel")

    def test_renders_escaped_and_works_with_as(self):
        self.practice.subtitle_en = "A & B"
        html = Template(
            '{% load payment_tags %}{% doc_field p "subtitle" lang %}|'
            '{% doc_field p "subtitle" lang as s %}{{ s }}'
        ).render(Context({"p": self.practice, "lang": "en"}))
        self.assertEqual(html, "A &amp; B|A &amp; B")
