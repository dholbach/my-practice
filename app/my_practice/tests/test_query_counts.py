"""N+1 ratchets for the pages with the heaviest related-object access.

#276 found /analytics/ firing 4,088 queries in 2.3s from four separate causes.
Two query-count tests came out of that, one in test_views_analytics and one in
test_views_dashboard, but both asserted a fixed ceiling against fixed seed data
— see QueryCountMixin for why that is a weak shape. Both have been rewritten in
this module (Dashboard/Analytics below) and removed from their old homes, so
every query guard in the suite now has the same shape.

These assert the opposite property: rendering the same page with more rows must
not issue more queries. That is exactly what an N+1 breaks, and it holds no
matter what the baseline count happens to be, so it neither drifts nor needs a
magic number.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import (
    Client,
    Invoice,
    InvoiceItem,
    Practice,
    PracticeTodo,
    ServiceType,
    Session,
)
from .test_helpers import QueryCountMixin, link_user_to_practice


class QueryCountTestBase(QueryCountMixin, TestCase):
    """Practice, user and a logged-in test client scoped to that practice."""

    slug = "query-counts"

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug=self.slug,
            title="Test Practitioner",
            email="test@practice.example",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="qcuser", password="testpass123")
        link_user_to_practice(self.user, self.practice)

        self.http = TestClient()
        self.http.login(username="qcuser", password="testpass123")
        session = self.http.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

        self.service_type = ServiceType.objects.create(
            code="individual",
            name="60 Min Session",
            practice=self.practice,
        )

    def make_client(self, code):
        return Client.objects.create(
            practice=self.practice,
            client_code=code,
            full_name=f"Client {code}",
            email=f"{code.lower()}@example.com",
            hourly_rate_60=Decimal("90.00"),
        )

    def make_invoice(self, client, number, days_ago=0, paid=False):
        """Create an invoice with one 60-minute item.

        `paid` matters for the analytics page: several of its panels count only
        paid invoices, so a queryset of sent ones leaves them empty and any N+1
        inside them dormant.
        """
        invoice = Invoice.objects.create(
            practice=self.practice,
            client=client,
            invoice_number=number,
            invoice_date=date.today() - timedelta(days=days_ago),
            status=Invoice.Status.PAID if paid else Invoice.Status.SENT,
            total=Decimal("90.00"),
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=client,
                session_date=date.today() - timedelta(days=days_ago),
                duration=60,
            ),
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
            total=Decimal("90.00"),
        )
        return invoice


class InvoiceListQueryCountTest(QueryCountTestBase):
    slug = "query-counts-invoices"

    def test_invoice_list_does_not_query_per_invoice(self):
        # paginate_by is 20, so five and ten invoices both render in full on
        # page one — any growth is per-row work, not a second page.
        client = self.make_client("IL")
        for i in range(5):
            self.make_invoice(client, f"IL-{i}", days_ago=i)

        def add_rows():
            for i in range(5, 10):
                self.make_invoice(client, f"IL-{i}", days_ago=i)

        self.assertQueryCountStable(
            lambda: self.http.get(reverse("invoice_list")),
            add_rows,
            label="Invoice list",
        )

    def test_invoice_list_does_not_query_per_client(self):
        # A distinct client per invoice is the shape that catches a missing
        # select_related("client") specifically, rather than any per-row work.
        for i in range(5):
            self.make_invoice(self.make_client(f"C{i}"), f"CL-{i}", days_ago=i)

        def add_rows():
            for i in range(5, 10):
                self.make_invoice(self.make_client(f"C{i}"), f"CL-{i}", days_ago=i)

        self.assertQueryCountStable(
            lambda: self.http.get(reverse("invoice_list")),
            add_rows,
            label="Invoice list (distinct clients)",
        )


class ClientListQueryCountTest(QueryCountTestBase):
    slug = "query-counts-clients"

    def test_client_list_does_not_query_per_client(self):
        # ClientListView deliberately has no pagination, so every client is
        # rendered and a per-row query shows up directly.
        for i in range(5):
            self.make_invoice(self.make_client(f"A{i}"), f"A{i}-1")

        def add_rows():
            for i in range(5, 10):
                self.make_invoice(self.make_client(f"A{i}"), f"A{i}-1")

        self.assertQueryCountStable(
            lambda: self.http.get(reverse("client_list")),
            add_rows,
            label="Client list",
        )


class ClientDetailQueryCountTest(QueryCountTestBase):
    slug = "query-counts-detail"

    def test_client_detail_does_not_query_per_session(self):
        # The page the v0.5.1 redesign reshaped: one client, many sessions and
        # invoices across the tabs. Scaling here is rows *within* one client.
        self.client_obj = self.make_client("CD")
        for i in range(5):
            self.make_invoice(self.client_obj, f"CD-{i}", days_ago=i)

        def add_rows():
            for i in range(5, 12):
                self.make_invoice(self.client_obj, f"CD-{i}", days_ago=i)

        self.assertQueryCountStable(
            lambda: self.http.get(reverse("client_detail", kwargs={"pk": self.client_obj.pk})),
            add_rows,
            label="Client detail",
        )


class FocusQueueQueryCountTest(QueryCountTestBase):
    slug = "query-counts-focus"

    def setUp(self):
        super().setUp()
        self.client_obj = self.make_client("FQ")
        self.invoice_type = ContentType.objects.get_for_model(Invoice)

    def _make_plain_task(self, index):
        return PracticeTodo.objects.create(
            practice=self.practice,
            title=f"Task {index}",
            due_date=timezone.localdate() + timedelta(days=index),
        )

    def _make_linked_task(self, index):
        """A task pointing at its own Invoice through the generic relation.

        This is the shape the queue actually holds: sync_focus_queue_tasks
        materialises one task per unpaid invoice / missing session log, and the
        template resolves related_object_url on each row. A plain task has
        related_object None, so it would never touch the generic FK at all and
        the prefetch that makes this page O(1) would go untested.
        """
        invoice = self.make_invoice(self.client_obj, f"FQ-{index}", days_ago=index)
        return PracticeTodo.objects.create(
            practice=self.practice,
            title=f"Unpaid {index}",
            content_type=self.invoice_type,
            object_id=invoice.pk,
        )

    def test_focus_queue_does_not_query_per_task(self):
        # paginate_by is 50, so both measurements render on page one.
        for i in range(5):
            self._make_plain_task(i)

        def add_rows():
            for i in range(5, 15):
                self._make_plain_task(i)

        self.assertQueryCountStable(
            lambda: self.http.get(reverse("focus_queue")),
            add_rows,
            label="Focus Queue",
        )

    def test_focus_queue_does_not_query_per_related_object(self):
        # The queryset select_relates content_type and prefetches
        # related_object precisely so this stays flat; drop either and each row
        # resolves its own invoice.
        for i in range(5):
            self._make_linked_task(i)

        def add_rows():
            for i in range(5, 15):
                self._make_linked_task(i)

        self.assertQueryCountStable(
            lambda: self.http.get(reverse("focus_queue")),
            add_rows,
            label="Focus Queue (tasks with related objects)",
        )


class DashboardQueryCountTest(QueryCountTestBase):
    slug = "query-counts-dashboard"

    def test_dashboard_does_not_query_per_invoice(self):
        # Replaces test_views_dashboard.test_dashboard_query_count, which seeded
        # five clients and allowed 85 queries against an actual ~74. An N+1 over
        # those five rows adds about five queries and lands inside the headroom,
        # so the ceiling could not fail for the reason it was written.
        #
        # recent_invoices is sliced [:10], so both measurements are kept at or
        # below the cap: the rendered list grows from five rows to ten and a
        # per-row query in it shows up, instead of being masked by the slice.
        for i in range(5):
            self.make_invoice(self.make_client(f"D{i}"), f"D{i}-1")

        def add_rows():
            for i in range(5, 10):
                self.make_invoice(self.make_client(f"D{i}"), f"D{i}-1")

        self.assertQueryCountStable(
            lambda: self.http.get(reverse("dashboard")),
            add_rows,
            label="Dashboard",
        )


class AnalyticsQueryCountTest(QueryCountTestBase):
    slug = "query-counts-analytics"

    def test_analytics_does_not_query_per_invoice(self):
        # Replaces test_views_analytics.test_analytics_dashboard_performance and
        # its ceiling of 360, which was loose enough to absorb an N+1 over the
        # five rows it seeded several times over.
        #
        # Every invoice is dated today deliberately. AnalyticsDashboardBuilder
        # loops over the years its data spans (_get_yearly_timeoff_breakdown
        # queries once per year), so seeding across years would grow the count
        # for a bounded, legitimate reason and make the assertion meaningless.
        # Holding the span at one year isolates per-row growth, which is the
        # thing being guarded.
        #
        # They are paid, which is load-bearing rather than incidental: the
        # top-clients panel filters on status="paid", so an unpaid fixture
        # renders it empty and the test passes without ever entering the code
        # it most needs to guard. Written with sent invoices first, this test
        # was green against a live N+1 in ClientAnalyzer.get_top_by_revenue.
        def seed(start, stop):
            for i in range(start, stop):
                self.make_invoice(self.make_client(f"AN{i}"), f"AN{i}-1", paid=True)

        seed(0, 5)

        def add_rows():
            seed(5, 12)

        self.assertQueryCountStable(
            lambda: self.http.get(reverse("analytics")),
            add_rows,
            label="Analytics",
        )
