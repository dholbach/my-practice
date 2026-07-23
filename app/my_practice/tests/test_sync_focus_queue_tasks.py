"""Tests for the sync_focus_queue_tasks management command (P-050 phase 2)."""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ..models import (
    Client,
    ClientTag,
    Invoice,
    InvoiceItem,
    OperationalChecklistCompletion,
    Practice,
    PracticeTodo,
    ServiceType,
    Session,
)


def _make_practice(name="Test Practice"):
    return Practice.objects.create(name=name, title="Testtherapeutin")


def _period_start(checklist_type: str) -> date:
    """Return the current period start for a checklist type (mirrors ChecklistWidgetBuilder)."""
    today = date.today()
    if checklist_type == "weekly":
        return today - timedelta(days=today.weekday())
    elif checklist_type == "monthly":
        return date(today.year, today.month, 1)
    elif checklist_type == "quarterly":
        q = ((today.month - 1) // 3) * 3 + 1
        return date(today.year, q, 1)
    else:  # annual
        return date(today.year, 1, 1)


def _make_client(practice, code="XX-1"):
    return Client.objects.create(
        practice=practice,
        client_code=code,
        full_name="Test Klient",
        hourly_rate_60=Decimal("100.00"),
    )


def _make_invoice(practice, client, status, days_ago, number):
    inv_date = date.today() - timedelta(days=days_ago)
    invoice = Invoice.objects.create(
        practice=practice,
        client=client,
        invoice_number=number,
        invoice_date=inv_date,
        status=status,
    )
    service, _ = ServiceType.objects.get_or_create(
        code="test-session", defaults={"name": "Session"}
    )
    session = Session.objects.create(
        client=client, session_date=inv_date - timedelta(days=1), duration=60
    )
    InvoiceItem.objects.create(
        invoice=invoice, session=session, service_type=service, quantity=1, rate=Decimal("100.00")
    )
    return invoice


class SyncMissingSessionLogTests(TestCase):
    def setUp(self):
        self.practice = _make_practice()
        self.client_obj = _make_client(self.practice)
        self.tag = ClientTag.objects.create(name="missing-session-log", color="red")

    def test_creates_task_for_tagged_client(self):
        self.client_obj.tags.add(self.tag)
        call_command("sync_focus_queue_tasks")

        task = PracticeTodo.objects.get(task_type=PracticeTodo.TaskType.MISSING_SESSION_LOG)
        self.assertEqual(task.title, "XX-1")
        self.assertEqual(task.related_object, self.client_obj)
        self.assertFalse(task.is_completed)

    def test_no_task_for_untagged_client(self):
        call_command("sync_focus_queue_tasks")
        self.assertFalse(
            PracticeTodo.objects.filter(
                task_type=PracticeTodo.TaskType.MISSING_SESSION_LOG
            ).exists()
        )

    def test_auto_closes_when_tag_removed(self):
        self.client_obj.tags.add(self.tag)
        call_command("sync_focus_queue_tasks")
        task = PracticeTodo.objects.get(task_type=PracticeTodo.TaskType.MISSING_SESSION_LOG)

        self.client_obj.tags.remove(self.tag)
        call_command("sync_focus_queue_tasks")

        task.refresh_from_db()
        self.assertTrue(task.is_completed)

    def test_idempotent_no_duplicate_task(self):
        self.client_obj.tags.add(self.tag)
        call_command("sync_focus_queue_tasks")
        call_command("sync_focus_queue_tasks")
        self.assertEqual(
            PracticeTodo.objects.filter(
                task_type=PracticeTodo.TaskType.MISSING_SESSION_LOG
            ).count(),
            1,
        )

    def test_practice_isolation(self):
        other_practice = _make_practice("Other Practice")
        other_client = _make_client(other_practice, "YY-2")
        other_client.tags.add(self.tag)
        call_command("sync_focus_queue_tasks")

        self.assertFalse(
            PracticeTodo.objects.filter(
                practice=self.practice, task_type=PracticeTodo.TaskType.MISSING_SESSION_LOG
            ).exists()
        )
        self.assertTrue(
            PracticeTodo.objects.filter(
                practice=other_practice, task_type=PracticeTodo.TaskType.MISSING_SESSION_LOG
            ).exists()
        )


class SyncInvoiceUnpaidTests(TestCase):
    def setUp(self):
        self.practice = _make_practice()
        self.client_obj = _make_client(self.practice)

    def test_creates_task_for_overdue_invoice(self):
        invoice = _make_invoice(self.practice, self.client_obj, "sent", 40, "INV-040")
        call_command("sync_focus_queue_tasks")

        task = PracticeTodo.objects.get(task_type=PracticeTodo.TaskType.INVOICE_UNPAID)
        self.assertEqual(task.title, "INV-040")
        self.assertEqual(task.related_object, invoice)

    def test_no_task_for_recently_sent_invoice(self):
        _make_invoice(self.practice, self.client_obj, "sent", 10, "INV-010")
        call_command("sync_focus_queue_tasks")
        self.assertFalse(
            PracticeTodo.objects.filter(task_type=PracticeTodo.TaskType.INVOICE_UNPAID).exists()
        )

    def test_auto_closes_when_paid(self):
        invoice = _make_invoice(self.practice, self.client_obj, "sent", 40, "INV-041")
        call_command("sync_focus_queue_tasks")
        task = PracticeTodo.objects.get(task_type=PracticeTodo.TaskType.INVOICE_UNPAID)

        invoice.status = "paid"
        invoice.save(update_fields=["status"])
        call_command("sync_focus_queue_tasks")

        task.refresh_from_db()
        self.assertTrue(task.is_completed)


class SyncInvoiceUnsentTests(TestCase):
    def setUp(self):
        self.practice = _make_practice()
        self.client_obj = _make_client(self.practice)

    def test_creates_task_for_draft_invoice(self):
        invoice = _make_invoice(self.practice, self.client_obj, "draft", 5, "INV-DRF")
        call_command("sync_focus_queue_tasks")

        task = PracticeTodo.objects.get(task_type=PracticeTodo.TaskType.INVOICE_UNSENT)
        self.assertEqual(task.title, "INV-DRF")
        self.assertEqual(task.related_object, invoice)

    def test_auto_closes_when_sent(self):
        invoice = _make_invoice(self.practice, self.client_obj, "draft", 5, "INV-DR2")
        call_command("sync_focus_queue_tasks")
        task = PracticeTodo.objects.get(task_type=PracticeTodo.TaskType.INVOICE_UNSENT)

        invoice.status = "sent"
        invoice.save(update_fields=["status"])
        call_command("sync_focus_queue_tasks")

        task.refresh_from_db()
        self.assertTrue(task.is_completed)


class SyncOperationalChecklistTests(TestCase):
    def setUp(self):
        self.practice = _make_practice()

    def test_creates_single_aggregate_task_when_pending(self):
        call_command("sync_focus_queue_tasks")
        task = PracticeTodo.objects.get(task_type=PracticeTodo.TaskType.OPERATIONAL_CHECKLIST)
        self.assertIn("monthly", task.title)

    def test_idempotent_single_task(self):
        call_command("sync_focus_queue_tasks")
        call_command("sync_focus_queue_tasks")
        self.assertEqual(
            PracticeTodo.objects.filter(
                task_type=PracticeTodo.TaskType.OPERATIONAL_CHECKLIST
            ).count(),
            1,
        )

    def test_auto_closes_when_all_cadences_completed(self):
        call_command("sync_focus_queue_tasks")
        task = PracticeTodo.objects.get(task_type=PracticeTodo.TaskType.OPERATIONAL_CHECKLIST)

        for checklist_type in ("monthly", "weekly", "quarterly", "annual"):
            OperationalChecklistCompletion.objects.create(
                checklist_type=checklist_type,
                year_month=_period_start(checklist_type),
                completed_at=timezone.now(),
            )
        call_command("sync_focus_queue_tasks")

        task.refresh_from_db()
        self.assertTrue(task.is_completed)
