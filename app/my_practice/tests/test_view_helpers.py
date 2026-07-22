"""Tests for view_helpers utility functions."""

from django.test import RequestFactory, TestCase
from my_practice.utils.view_helpers import get_year_from_request


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
