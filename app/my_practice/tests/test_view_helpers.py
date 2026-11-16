"""Tests for view_helpers utility functions."""

import json

from django.test import RequestFactory, TestCase
from django.utils.functional import lazy

from my_practice.utils.view_helpers import get_year_from_request, json_error


class JsonErrorTests(TestCase):
    def test_default_is_a_400_with_success_false(self):
        response = json_error("Nope")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content), {"success": False, "error": "Nope"})

    def test_status_is_passed_through(self):
        self.assertEqual(json_error("Gone", 404).status_code, 404)

    def test_lazy_strings_and_exceptions_become_text(self):
        lazy_text = lazy(lambda: "Deferred text", str)()
        self.assertEqual(json.loads(json_error(lazy_text).content)["error"], "Deferred text")
        self.assertEqual(
            json.loads(json_error(ValueError("bad file")).content)["error"], "bad file"
        )


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
