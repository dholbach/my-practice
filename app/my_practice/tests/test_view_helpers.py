"""Tests for view_helpers utility functions."""

from datetime import date

from django.test import RequestFactory, TestCase
from my_practice.models import Practice
from my_practice.utils.view_helpers import (
    get_date_range_from_request,
    get_search_query_filter,
    get_year_from_request,
    paginate_queryset,
)


class DateRangeTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_valid_date_range(self):
        request = self.factory.get("/", {"start_date": "2026-01-01", "end_date": "2026-03-31"})
        start, end = get_date_range_from_request(request)
        self.assertEqual(start, date(2026, 1, 1))
        self.assertEqual(end, date(2026, 3, 31))

    def test_invalid_dates_return_none(self):
        request = self.factory.get("/", {"start_date": "not-a-date", "end_date": "also-bad"})
        start, end = get_date_range_from_request(request)
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_missing_dates_return_none(self):
        request = self.factory.get("/")
        start, end = get_date_range_from_request(request)
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_custom_param_names(self):
        request = self.factory.get("/", {"von": "2026-01-01", "bis": "2026-12-31"})
        start, end = get_date_range_from_request(request, start_param="von", end_param="bis")
        self.assertEqual(start, date(2026, 1, 1))
        self.assertEqual(end, date(2026, 12, 31))


class YearFromRequestTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_valid_year(self):
        request = self.factory.get("/", {"year": "2026"})
        self.assertEqual(get_year_from_request(request), 2026)

    def test_invalid_year_returns_default(self):
        request = self.factory.get("/", {"year": "abc"})
        self.assertIsNone(get_year_from_request(request))

    def test_out_of_range_year_returns_default(self):
        request = self.factory.get("/", {"year": "1999"})
        self.assertIsNone(get_year_from_request(request))

    def test_missing_year_returns_default(self):
        request = self.factory.get("/")
        self.assertEqual(get_year_from_request(request, default=2025), 2025)

    def test_custom_param_name(self):
        request = self.factory.get("/", {"jahr": "2024"})
        self.assertEqual(get_year_from_request(request, param="jahr"), 2024)


class SearchQueryFilterTests(TestCase):
    def test_returns_empty_q_for_none(self):
        q = get_search_query_filter(None, ["name"])
        # An empty Q() matches everything — check no conditions added
        self.assertFalse(q.children)

    def test_returns_empty_q_for_empty_string(self):
        q = get_search_query_filter("", ["name"])
        self.assertFalse(q.children)

    def test_single_field_filter(self):
        q = get_search_query_filter("test", ["full_name"])
        self.assertTrue(q.children)

    def test_multiple_fields_uses_or(self):
        q = get_search_query_filter("test", ["full_name", "client_code"])
        # Should produce OR of two icontains conditions
        self.assertEqual(len(q.children), 2)


class PaginateQuerysetTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_returns_first_page_by_default(self):
        from my_practice.models import Practice

        for i in range(5):
            Practice.objects.create(name=f"Practice {i}", slug=f"practice-{i}")

        request = self.factory.get("/")
        page_obj, paginator = paginate_queryset(
            request, Practice.objects.order_by("name"), per_page=2
        )
        self.assertEqual(page_obj.number, 1)
        self.assertEqual(paginator.num_pages, 3)

    def test_invalid_page_returns_first(self):
        for i in range(3):
            Practice.objects.create(name=f"P {i}", slug=f"p-{i}")

        request = self.factory.get("/", {"page": "not-a-number"})
        page_obj, _ = paginate_queryset(request, Practice.objects.order_by("name"), per_page=2)
        self.assertEqual(page_obj.number, 1)

    def test_excessive_page_returns_last(self):
        for i in range(3):
            Practice.objects.create(name=f"Q {i}", slug=f"q-{i}")

        request = self.factory.get("/", {"page": "9999"})
        page_obj, paginator = paginate_queryset(
            request, Practice.objects.order_by("name"), per_page=2
        )
        self.assertEqual(page_obj.number, paginator.num_pages)
