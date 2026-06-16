"""
Signals for automatic invoice total calculation
================================================
Automatically recalculates Invoice.total when InvoiceItems are saved or deleted.
Also syncs Session.cancelled and Session.group_size from InvoiceItems (P-035).
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Invoice, InvoiceItem


@receiver(post_save, sender=InvoiceItem)
def update_invoice_total_on_save(
    sender,
    instance,
    **kwargs,  # noqa: ARG001, vulture
):  # pylint: disable=unused-argument
    """Recalculate invoice total when an invoice item is saved."""
    invoice = instance.invoice
    recalculate_invoice_total(invoice)
    sync_session_fields(instance)


@receiver(post_delete, sender=InvoiceItem)
def update_invoice_total_on_delete(
    sender,
    instance,
    **kwargs,  # noqa: ARG001, vulture
):  # pylint: disable=unused-argument
    """Recalculate invoice total when an invoice item is deleted."""
    invoice = instance.invoice
    recalculate_invoice_total(invoice)
    # On delete: re-derive cancelled/group_size from any remaining items on this session
    if instance.session_id:
        _resync_session(instance.session_id)


def recalculate_invoice_total(invoice):
    """
    Calculate and save the total for an invoice based on its items.

    Uses the existing Invoice.calculate_total() method and additionally
    updates invoice_date for draft invoices.
    """
    # Use the model's built-in calculation method
    # This sets subtotal, tax_amount, and total on the instance
    invoice.calculate_total()

    # Determine which fields to save
    update_fields = ["subtotal", "tax_amount", "total"]

    # Auto-update invoice_date to latest session date (only for drafts)
    if invoice.status == Invoice.Status.DRAFT:
        target_date = invoice.computed_invoice_date()
        if invoice.invoice_date != target_date:
            invoice.invoice_date = target_date
            update_fields.append("invoice_date")

    # Save only the calculated fields
    invoice.save(update_fields=update_fields)


def sync_session_fields(item: InvoiceItem) -> None:
    """
    Sync Session.cancelled and Session.group_size from a saved InvoiceItem (P-035).

    - cancelled is True if this item OR any sibling item on the same session
      has a service_type with "cancel" in its code.
    - group_size is the max group_size across all items on the same session.

    This ensures Session always reflects the latest billing state.
    """
    if not item.session_id:
        return
    _resync_session(item.session_id)


def _resync_session(session_id: int) -> None:
    """Recompute and persist cancelled + group_size for a Session from its InvoiceItems."""
    from django.db.models import Max

    from .models import Session

    sibling_items = InvoiceItem.objects.filter(session_id=session_id)
    if not sibling_items.exists():
        # No items left — reset to clean defaults
        Session.objects.filter(id=session_id).update(cancelled=False, group_size=1)
        return

    is_cancelled = sibling_items.filter(service_type__code__icontains="cancel").exists()
    max_group_size = sibling_items.aggregate(m=Max("group_size"))["m"] or 1

    Session.objects.filter(id=session_id).update(
        cancelled=is_cancelled,
        group_size=max_group_size,
    )
