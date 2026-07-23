"""
Management command to materialize derived Task rows for the P-050 Focus Queue.

Creates a PracticeTodo (task_type != manual) for each currently-outstanding
derived signal (missing session log, unpaid/unsent invoices, pending
operational checklists) and auto-closes ones whose underlying signal has
since resolved. Reuses the same detection logic as the dashboard's "Braucht
Aktion" widget builders rather than re-deriving it.

Titles for materialized tasks are intentionally language-neutral (client
codes, invoice numbers, raw checklist-type keys) rather than translated
prose — this command runs outside any request/session, so there is no
admin UI language to render into. Translated display formatting belongs in
the Focus Queue UI (P-050 phase 3), not in stored data here.

Not currently wired to a scheduled job (see other my-practice-*.timer units
in scripts/) — run manually until the Focus Queue UI (phase 3) is ready to
consume these rows.
"""

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db.models import Model, Q
from django.utils import timezone

from ...models import Invoice, Practice, PracticeTodo
from ...models.session import Session
from ...utils.dashboard_widgets import ChecklistWidgetBuilder, InvoiceActionsWidgetBuilder
from ...utils.tag_helpers import get_sessions_missing_log


class Command(BaseCommand):
    help = (
        "Materialize derived Focus Queue Task rows (missing session log, "
        "unpaid/unsent invoices, operational checklists) and auto-close "
        "resolved ones."
    )

    def handle(self, *args, **options):
        totals = {"created": 0, "closed": 0}

        for practice in Practice.objects.filter(is_active=True):
            self._sync_missing_session_log(practice, totals)
            self._sync_invoice_unpaid(practice, totals)
            self._sync_invoice_unsent(practice, totals)
            self._sync_operational_checklist(practice, totals)

        self.stdout.write(
            self.style.SUCCESS(
                f"Focus queue sync: {totals['created']} created, {totals['closed']} closed"
            )
        )

    def _sync_object_tasks(
        self,
        practice: Practice,
        task_type: str,
        model: type[Model],
        objects: list,
        title_fn,
        totals: dict,
    ) -> None:
        """
        Ensure one open Task per object in `objects` (matched via the generic
        related_object FK), and auto-close open Tasks of this task_type whose
        object is no longer in `objects` — including ones left over from a
        previous version of this sync pointing at a different model (e.g.
        missing_session_log used to link Client, now links Session); those
        never match content_type+object_id for the current model, so they're
        stale by definition and get closed regardless of what they point at.
        """
        content_type = ContentType.objects.get_for_model(model)
        current_ids = {obj.pk for obj in objects}

        all_open = PracticeTodo.objects.filter(
            practice=practice,
            task_type=task_type,
            completed_at__isnull=True,
        )
        existing_ids = set(
            all_open.filter(content_type=content_type).values_list("object_id", flat=True)
        )

        totals["closed"] += all_open.exclude(
            Q(content_type=content_type) & Q(object_id__in=current_ids)
        ).update(completed_at=timezone.now())

        for obj in objects:
            if obj.pk in existing_ids:
                continue
            PracticeTodo.objects.create(
                practice=practice,
                title=title_fn(obj),
                task_type=task_type,
                related_object=obj,
            )
            totals["created"] += 1

    def _sync_missing_session_log(self, practice: Practice, totals: dict) -> None:
        sessions = list(get_sessions_missing_log(practice))
        self._sync_object_tasks(
            practice,
            PracticeTodo.TaskType.MISSING_SESSION_LOG,
            Session,
            sessions,
            lambda session: session.client.client_code,
            totals,
        )

    def _sync_invoice_unpaid(self, practice: Practice, totals: dict) -> None:
        invoices = InvoiceActionsWidgetBuilder(practice).get_overdue_invoices()
        self._sync_object_tasks(
            practice,
            PracticeTodo.TaskType.INVOICE_UNPAID,
            Invoice,
            invoices,
            lambda invoice: invoice.invoice_number,
            totals,
        )

    def _sync_invoice_unsent(self, practice: Practice, totals: dict) -> None:
        invoices = list(InvoiceActionsWidgetBuilder(practice).get_draft_invoices())
        self._sync_object_tasks(
            practice,
            PracticeTodo.TaskType.INVOICE_UNSENT,
            Invoice,
            invoices,
            lambda invoice: invoice.invoice_number,
            totals,
        )

    def _sync_operational_checklist(self, practice: Practice, totals: dict) -> None:
        """
        Operational checklists (backups, security review) aren't tied to a
        Client/Invoice and aren't practice-specific by nature — but Task rows
        require a practice FK, so one Task is materialized per active
        practice, mirroring how the dashboard widget itself is practice-
        agnostic. A single open Task represents all currently-pending
        cadences at once (same aggregation the widget already does), rather
        than one row per cadence.
        """
        pending = ChecklistWidgetBuilder().build_context()["pending_checklists"]

        existing = (
            PracticeTodo.objects.filter(
                practice=practice,
                task_type=PracticeTodo.TaskType.OPERATIONAL_CHECKLIST,
                completed_at__isnull=True,
            )
            .order_by("created_at")
            .first()
        )

        if not pending:
            if existing:
                existing.mark_completed()
                totals["closed"] += 1
            return

        title = ", ".join(entry["type"] for entry in pending)
        if existing:
            if existing.title != title:
                existing.title = title
                existing.save(update_fields=["title"])
        else:
            PracticeTodo.objects.create(
                practice=practice,
                title=title,
                task_type=PracticeTodo.TaskType.OPERATIONAL_CHECKLIST,
            )
            totals["created"] += 1
