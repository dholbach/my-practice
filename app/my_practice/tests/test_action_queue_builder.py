"""Tests for ActionQueueBuilder (P-117 chunk 1)."""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from ..models import (
    Client,
    ClientTag,
    Invoice,
    InvoiceItem,
    Practice,
    ServiceType,
    Session,
)
from ..utils.action_queue_builder import ActionQueueBuilder


def _make_practice(slug="aq-test"):
    return Practice.objects.create(
        name="Testpraxis",
        slug=slug,
        title="Heilpraktikerin",
        email="test@practice.example",
        city="Berlin",
    )


def _make_client(practice, code="TC-1"):
    return Client.objects.create(
        practice=practice,
        client_code=code,
        full_name="Test Klient",
        hourly_rate_60=Decimal("100.00"),
    )


def _make_invoice(practice, client, status="sent", days_ago=35, number="INV-001"):
    inv_date = date.today() - timedelta(days=days_ago)
    inv = Invoice.objects.create(
        practice=practice,
        client=client,
        invoice_number=number,
        invoice_date=inv_date,
        status=status,
    )
    service, _ = ServiceType.objects.get_or_create(
        code="test-session",
        defaults={"name": "Session"},
    )
    session = Session.objects.create(
        client=client,
        session_date=inv_date - timedelta(days=1),
        duration=60,
    )
    InvoiceItem.objects.create(
        invoice=inv,
        session=session,
        service_type=service,
        quantity=1,
        rate=Decimal("100.00"),
    )
    return inv


class ActionQueueBuilderOverdueTest(TestCase):
    """Overdue invoices appear as priority-1 INVOICE items with Mahnen action."""

    def setUp(self):
        self.practice = _make_practice("aq-overdue")
        self.client = _make_client(self.practice, "OD-1")
        self.invoice = _make_invoice(
            self.practice, self.client, status="sent", days_ago=40, number="INV-040"
        )

    def test_overdue_invoice_in_queue(self):
        items = ActionQueueBuilder(self.practice).build()
        overdue = [i for i in items if i["category"] == "INVOICE" and i["priority"] == 1]
        self.assertEqual(len(overdue), 1)
        self.assertIn("INV-040", overdue[0]["summary"])

    def test_overdue_action_is_payment_reminder(self):
        items = ActionQueueBuilder(self.practice).build()
        overdue = [i for i in items if i["category"] == "INVOICE" and i["priority"] == 1]
        expected_url = reverse("send_payment_reminder", kwargs={"pk": self.client.pk})
        self.assertEqual(overdue[0]["action_url"], expected_url)
        self.assertEqual(overdue[0]["action_label"], "Mahnen")

    def test_overdue_sub_text_contains_client_code(self):
        items = ActionQueueBuilder(self.practice).build()
        overdue = [i for i in items if i["category"] == "INVOICE" and i["priority"] == 1]
        self.assertIn("OD-1", overdue[0]["sub_text"])

    def test_non_overdue_sent_invoice_is_priority_2(self):
        """Invoice sent 10 days ago is unpaid but not overdue — priority 2."""
        client2 = _make_client(self.practice, "ND-2")
        _make_invoice(self.practice, client2, status="sent", days_ago=10, number="INV-010")
        items = ActionQueueBuilder(self.practice).build()
        non_overdue = [
            i
            for i in items
            if i["category"] == "INVOICE" and i["priority"] == 2 and "INV-010" in i["summary"]
        ]
        self.assertEqual(len(non_overdue), 1)

    def test_paid_invoice_not_in_queue(self):
        client3 = _make_client(self.practice, "PD-3")
        _make_invoice(self.practice, client3, status="paid", days_ago=5, number="INV-005")
        items = ActionQueueBuilder(self.practice).build()
        summaries = [i["summary"] for i in items]
        self.assertFalse(any("INV-005" in s for s in summaries))


class ActionQueueBuilderDraftTest(TestCase):
    """Draft invoices appear as priority-2 DRAFT items."""

    def setUp(self):
        self.practice = _make_practice("aq-draft")
        self.client = _make_client(self.practice, "DR-1")
        self.invoice = _make_invoice(
            self.practice, self.client, status="draft", days_ago=5, number="INV-DRF"
        )

    def test_draft_invoice_in_queue(self):
        items = ActionQueueBuilder(self.practice).build()
        drafts = [i for i in items if i["category"] == "DRAFT"]
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0]["priority"], 2)
        self.assertIn("INV-DRF", drafts[0]["summary"])

    def test_draft_action_is_invoice_edit(self):
        items = ActionQueueBuilder(self.practice).build()
        drafts = [i for i in items if i["category"] == "DRAFT"]
        expected_url = reverse("invoice_edit", kwargs={"pk": self.invoice.pk})
        self.assertEqual(drafts[0]["action_url"], expected_url)
        self.assertEqual(drafts[0]["action_label"], "Fertigstellen")


class ActionQueueBuilderClientTest(TestCase):
    """Clients with attention tags appear as priority-2 CLIENT items."""

    def setUp(self):
        self.practice = _make_practice("aq-client")
        self.client = _make_client(self.practice, "FU-1")
        self.tag = ClientTag.objects.create(name="follow-up", color="orange")
        self.client.tags.add(self.tag)

    def test_follow_up_client_in_queue(self):
        items = ActionQueueBuilder(self.practice).build()
        client_items = [i for i in items if i["category"] == "CLIENT"]
        self.assertTrue(len(client_items) >= 1)
        codes = [i["summary"].split(" — ")[0] for i in client_items]
        self.assertIn("FU-1", codes)

    def test_client_action_links_to_detail(self):
        items = ActionQueueBuilder(self.practice).build()
        client_items = [i for i in items if i["category"] == "CLIENT" and "FU-1" in i["summary"]]
        self.assertTrue(client_items)
        expected_url = reverse("client_detail", kwargs={"pk": self.client.pk})
        self.assertEqual(client_items[0]["action_url"], expected_url)


class ActionQueueBuilderSortingTest(TestCase):
    """Priority-1 items sort before priority-2 items."""

    def setUp(self):
        self.practice = _make_practice("aq-sort")
        self.client = _make_client(self.practice, "ST-1")
        _make_invoice(self.practice, self.client, status="sent", days_ago=40, number="INV-OLD")
        client2 = _make_client(self.practice, "ST-2")
        _make_invoice(self.practice, client2, status="draft", days_ago=2, number="INV-DRF")

    def test_urgent_items_first(self):
        items = ActionQueueBuilder(self.practice).build()
        priorities = [i["priority"] for i in items]
        self.assertEqual(priorities, sorted(priorities))

    def test_items_have_required_keys(self):
        items = ActionQueueBuilder(self.practice).build()
        required = {
            "priority",
            "category",
            "category_label",
            "summary",
            "sub_text",
            "action_url",
            "action_label",
        }
        for item in items:
            self.assertEqual(required, set(item.keys()), msg=f"Missing keys in {item}")

    def test_sort_key_stripped_from_output(self):
        items = ActionQueueBuilder(self.practice).build()
        for item in items:
            self.assertNotIn("_sort_key", item)


class ActionQueueBuilderEmptyTest(TestCase):
    """Empty practice has no invoice or client action items."""

    def test_no_invoice_or_client_items(self):
        practice = _make_practice("aq-empty")
        items = ActionQueueBuilder(practice).build()
        billing_client = [i for i in items if i["category"] in ("INVOICE", "DRAFT", "CLIENT")]
        self.assertEqual(billing_client, [])
