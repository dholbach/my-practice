"""Admin change lists cost the same number of queries for one row or several.

The list columns of Session (log, invoice item), Client (practice, tags) and Invoice
(client) read related rows; without ``select_related``/``prefetch_related`` each row adds
queries. Counting the queries for a page of one row and a page of four catches a column
that falls back to a query per row.
"""

from datetime import date

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from ..models import ClientTag, Invoice, Session
from .test_helpers import create_test_client, create_test_practice


class AdminListQueryTests(TestCase):
    def setUp(self):
        self.practice = create_test_practice()
        self.tag = ClientTag.objects.create(name="admin-list", slug="admin-list")
        User.objects.create_superuser("admin-list", "admin@example.com", "testpass123")
        self.client.login(username="admin-list", password="testpass123")

    def _add_row(self, code: str) -> None:
        client = create_test_client(self.practice, code=code)
        client.tags.add(self.tag)
        Session.objects.create(client=client, session_date=date(2026, 3, 1), duration=60)
        Invoice.objects.create(
            client=client,
            practice=self.practice,
            invoice_number=f"{code}-1",
            invoice_date=date(2026, 3, 1),
        )

    def _queries(self, name: str) -> int:
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse(f"admin:my_practice_{name}_changelist"))
        self.assertEqual(response.status_code, 200)
        return len(queries)

    def test_change_lists_do_not_query_per_row(self):
        self._add_row("XX-1")
        one_row = {name: self._queries(name) for name in ("session", "client", "invoice")}
        for code in ("XX-2", "XX-3", "XX-4"):
            self._add_row(code)
        for name, count in one_row.items():
            with self.subTest(model=name):
                self.assertEqual(self._queries(name), count)
