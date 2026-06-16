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
    Invoice,
    InquirySource,
    InquiryStatus,
    Practice,
    UserPractice,
)


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
        self.assertIn("label", first)


class GlobalSearchInquiryTest(TestCase):
    def setUp(self):
        self.user, self.practice = _setup_practice("search-inq", "srch_inq")
        self.http = TestClient()
        self.http.login(username="srch_inq", password="pass")

    def test_open_inquiry_appears_in_client_search(self):
        _make_inquiry(self.practice, name="Laura Liebig", status=InquiryStatus.NEW)
        resp = self.http.get(reverse("global_search"), {"q": "c:Laura"})
        labels = [r["label"] for r in resp.json()["results"]]
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
        self.assertIn("label", inquiries[0])

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
