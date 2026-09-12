"""
Tests for global search view (/api/search/).
Covers: prefix parsing, client/inquiry/invoice results, practice isolation, empty query.
"""

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import (
    Client,
    ClientInquiry,
    InquirySource,
    InquiryStatus,
    Invoice,
    Practice,
    UserPractice,
)


def _display(result):
    """Join a result back into the string the palette renders.

    Results are returned split as prefix + name + suffix so the palette can give
    the personal name its own privacy treatment; tests that only care about
    identity read the joined form.
    """
    return f"{result['prefix']}{result['name']}{result['suffix']}"


def _setup_practice(slug, username):
    user = User.objects.create_user(username=username, password="pass")
    practice = Practice.objects.create(name=f"Praxis {slug}", slug=slug)
    UserPractice.objects.create(user=user, practice=practice, is_owner=True)
    return user, practice


def _make_client(practice, code, name="Max Mustermann", active=True):
    return Client.objects.create(
        client_code=code,
        full_name=name,
        email=f"{code.lower()}@example.com",
        active=active,
        practice=practice,
    )


def _make_invoice(client, number="INV-001"):
    return Invoice.objects.create(
        client=client,
        invoice_number=number,
        invoice_date="2026-04-01",
        practice=client.practice,
    )


def _make_inquiry(practice, name="Neue Anfrage", status=InquiryStatus.NEW):
    return ClientInquiry.objects.create(
        full_name=name,
        email="anfrage@example.com",
        source=InquirySource.WEBSITE,
        status=status,
        inquiry_date="2026-04-01",
        practice=practice,
    )


class GlobalSearchEmptyTest(TestCase):
    def setUp(self):
        self.user, self.practice = _setup_practice("search-empty", "srch_empty")
        self.http = TestClient()
        self.http.login(username="srch_empty", password="pass")

    def test_empty_query_returns_empty(self):
        resp = self.http.get(reverse("global_search"), {"q": ""})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["results"], [])

    def test_whitespace_query_returns_empty(self):
        resp = self.http.get(reverse("global_search"), {"q": "   "})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["results"], [])


class GlobalSearchClientPrefixTest(TestCase):
    def setUp(self):
        self.user, self.practice = _setup_practice("search-client", "srch_client")
        self.client_obj = _make_client(self.practice, "MU", "Maria Muster")
        _make_invoice(self.client_obj, "MU-1")
        self.http = TestClient()
        self.http.login(username="srch_client", password="pass")

    def test_c_prefix_returns_only_clients(self):
        resp = self.http.get(reverse("global_search"), {"q": "c:MU"})
        data = resp.json()
        types = {r["type"] for r in data["results"]}
        self.assertIn("client", types)
        self.assertNotIn("invoice", types)

    def test_i_prefix_returns_only_invoices(self):
        resp = self.http.get(reverse("global_search"), {"q": "i:MU"})
        data = resp.json()
        types = {r["type"] for r in data["results"]}
        self.assertIn("invoice", types)
        self.assertNotIn("client", types)

    def test_in_prefix_returns_only_invoices(self):
        resp = self.http.get(reverse("global_search"), {"q": "in:MU-1"})
        data = resp.json()
        types = {r["type"] for r in data["results"]}
        self.assertIn("invoice", types)
        self.assertNotIn("client", types)

    def test_no_prefix_returns_both(self):
        resp = self.http.get(reverse("global_search"), {"q": "MU"})
        data = resp.json()
        types = {r["type"] for r in data["results"]}
        self.assertIn("client", types)
        self.assertIn("invoice", types)

    def test_client_result_has_required_fields(self):
        resp = self.http.get(reverse("global_search"), {"q": "c:MU"})
        clients = [r for r in resp.json()["results"] if r["type"] == "client"]
        self.assertTrue(clients)
        first = clients[0]
        self.assertIn("id", first)
        self.assertIn("code", first)
        self.assertIn("url", first)
        self.assertIn("prefix", first)
        self.assertIn("name", first)
        self.assertIn("suffix", first)


class GlobalSearchInquiryTest(TestCase):
    def setUp(self):
        self.user, self.practice = _setup_practice("search-inq", "srch_inq")
        self.http = TestClient()
        self.http.login(username="srch_inq", password="pass")

    def test_open_inquiry_appears_in_client_search(self):
        _make_inquiry(self.practice, name="Laura Liebig", status=InquiryStatus.NEW)
        resp = self.http.get(reverse("global_search"), {"q": "c:Laura"})
        labels = [_display(r) for r in resp.json()["results"]]
        self.assertTrue(any("Laura" in lbl for lbl in labels))

    def test_closed_inquiry_not_included(self):
        _make_inquiry(self.practice, name="Closed Person", status=InquiryStatus.CONVERTED)
        resp = self.http.get(reverse("global_search"), {"q": "c:Closed"})
        types = {r["type"] for r in resp.json()["results"]}
        self.assertNotIn("inquiry", types)

    def test_inquiry_result_has_required_fields(self):
        _make_inquiry(self.practice, name="Hans Hilpert", status=InquiryStatus.WAITLIST)
        resp = self.http.get(reverse("global_search"), {"q": "c:Hans"})
        inquiries = [r for r in resp.json()["results"] if r["type"] == "inquiry"]
        self.assertTrue(inquiries)
        self.assertIn("url", inquiries[0])
        self.assertIn("prefix", inquiries[0])
        self.assertIn("name", inquiries[0])
        self.assertIn("suffix", inquiries[0])

    def test_active_clients_appear_before_inquiries(self):
        _make_client(self.practice, "LL", "Lena Lange")
        _make_inquiry(self.practice, name="Lena Lorenz", status=InquiryStatus.NEW)
        resp = self.http.get(reverse("global_search"), {"q": "c:Lena"})
        results = resp.json()["results"]
        types = [r["type"] for r in results]
        # Client must appear before inquiry
        client_idx = next((i for i, t in enumerate(types) if t == "client"), None)
        inquiry_idx = next((i for i, t in enumerate(types) if t == "inquiry"), None)
        if client_idx is not None and inquiry_idx is not None:
            self.assertLess(client_idx, inquiry_idx)


class GlobalSearchPracticeIsolationTest(TestCase):
    """Results must be scoped to the logged-in user's practice."""

    def setUp(self):
        self.user1, self.practice1 = _setup_practice("isolation-p1", "iso_user1")
        self.user2, self.practice2 = _setup_practice("isolation-p2", "iso_user2")

        _make_client(self.practice1, "P1", "Praxis Eins Klient")
        _make_client(self.practice2, "P2", "Praxis Zwei Klient")

        self.http = TestClient()
        self.http.login(username="iso_user1", password="pass")

    def test_only_own_practice_clients_returned(self):
        resp = self.http.get(reverse("global_search"), {"q": "c:Praxis"})
        codes = [r["code"] for r in resp.json()["results"] if r["type"] == "client"]
        self.assertIn("P1", codes)
        self.assertNotIn("P2", codes)


class MultiLexemeQueryTest(TestCase):
    """
    Regression: `SearchRank(...) > 0` was used as the match predicate, but
    ts_rank only returns exactly 0.0 for a *single*-lexeme query that misses.
    Any multi-lexeme miss scores 1e-20 — which is > 0 — so a two-word search, or
    anything Postgres splits on a hyphen ("KK-9" -> 'kk' & '-9'), matched every
    row in the table. The real hit was then buried among arbitrary rows, ordered
    by a rank that tied at 1e-20 across all of them.

    These cases all pass trivially against a single-lexeme query, which is why
    the bug survived the original suite.
    """

    def setUp(self):
        self.user, self.practice = _setup_practice("search-multi", "srch_multi")
        self.http = TestClient()
        self.http.login(username="srch_multi", password="pass")

        self.klaus = _make_client(self.practice, "KK", name="Klaus Kleber")
        self.other = _make_client(self.practice, "AA", name="Anna Andersson")
        _make_inquiry(self.practice, name="Bertha Beispiel")
        self.invoice = _make_invoice(self.klaus, number="KK-9")
        _make_invoice(self.other, number="AA-6")

    def _labels(self, q):
        resp = self.http.get(reverse("global_search"), {"q": q})
        self.assertEqual(resp.status_code, 200)
        return [_display(r) for r in resp.json()["results"]]

    def test_hyphenated_invoice_number_returns_only_that_invoice(self):
        labels = self._labels("KK-9")
        self.assertEqual(len(labels), 1, f"expected only KK-9, got {labels}")
        self.assertIn("KK-9", labels[0])

    def test_hyphenated_query_with_invoice_prefix(self):
        labels = self._labels("i:KK-9")
        self.assertEqual(len(labels), 1, f"expected only KK-9, got {labels}")
        self.assertIn("KK-9", labels[0])

    def test_hyphenated_query_matches_no_clients_or_inquiries(self):
        # "KK-9" is an invoice number; no client or inquiry should surface for it.
        self.assertEqual(self._labels("c:KK-9"), [])

    def test_two_word_miss_returns_nothing(self):
        self.assertEqual(self._labels("Zzz Qqq"), [])

    def test_two_word_partial_miss_returns_nothing(self):
        # plainto_tsquery ANDs the terms: one matching token is not a match.
        self.assertEqual(self._labels("Klaus Qqq"), [])

    def test_full_name_search_still_works(self):
        # The client, plus their invoice — _search_invoices matches on
        # client__full_name too, so both hits here are intended.
        labels = self._labels("Klaus Kleber")
        self.assertEqual(len(labels), 2, f"expected the client and their invoice, got {labels}")
        self.assertTrue(any("Klaus Kleber" in label for label in labels))
        self.assertTrue(any("KK-9" in label for label in labels))
        self.assertFalse(any("Anna" in label or "AA-6" in label for label in labels))


class ResultSplitTest(TestCase):
    """
    Results are prefix + name + suffix, not one display string, so the palette
    can blur the personal name on its own (privacy mode) while leaving codes,
    invoice numbers, dates and statuses legible. If `name` ever picks up
    non-personal text, or a code leaks into `name`, privacy mode silently blurs
    the wrong thing — which is invisible unless privacy mode is switched on.
    """

    def setUp(self):
        self.user, self.practice = _setup_practice("search-split", "srch_split")
        self.http = TestClient()
        self.http.login(username="srch_split", password="pass")
        self.client_obj = _make_client(self.practice, "MU", name="Max Mustermann")

    def _first(self, q, result_type):
        resp = self.http.get(reverse("global_search"), {"q": q})
        matches = [r for r in resp.json()["results"] if r["type"] == result_type]
        self.assertTrue(matches, f"no {result_type} result for {q!r}")
        return matches[0]

    def test_client_name_is_isolated_from_the_code(self):
        result = self._first("c:MU", "client")
        self.assertEqual(result["name"], "Max Mustermann")
        self.assertIn("MU", result["prefix"])
        self.assertNotIn("Mustermann", result["prefix"])
        self.assertNotIn("Mustermann", result["suffix"])
        self.assertEqual(_display(result), "👤 MU — Max Mustermann")

    def test_inquiry_name_is_isolated_from_the_status(self):
        _make_inquiry(self.practice, name="Anna Schmidt", status=InquiryStatus.NEW)
        result = self._first("c:Anna", "inquiry")
        self.assertEqual(result["name"], "Anna Schmidt")
        self.assertNotIn("Schmidt", result["prefix"])
        self.assertNotIn("Schmidt", result["suffix"])
        self.assertIn("(", result["suffix"], "status renders after the name")

    def test_invoice_row_carries_no_personal_name(self):
        _make_invoice(self.client_obj, number="MU-1")
        result = self._first("i:MU-1", "invoice")
        self.assertEqual(result["name"], "", "invoices are identified by code, not name")
        self.assertNotIn("Mustermann", _display(result))
        self.assertIn("MU-1", result["prefix"])
