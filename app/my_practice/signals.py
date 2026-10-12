"""
Signals for automatic invoice total calculation
================================================
Automatically recalculates Invoice.total when InvoiceItems are saved or deleted.
Also syncs Session.cancelled and Session.group_size from InvoiceItems (P-035).

Also guards issued invoices: once an Invoice leaves DRAFT its content and
line items are frozen, and it can only be deleted after the § 147 AO
retention period (see LOCKED_INVOICE_FIELDS in models/invoice.py). Signals
rather than model methods, so queryset deletes and the admin are covered too.

Also cleans up Practice.logo/signature files on the filesystem — ImageField
doesn't do this on its own, so without these signals every re-upload in
Practice settings leaves the previous file behind forever.
"""

from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.utils.translation import gettext as _

from .models import Invoice, InvoiceItem, InvoiceLockedError, Practice
from .models.invoice import LOCKED_INVOICE_FIELDS, issued_invoice_writes_allowed


def _locked_message(number: str) -> str:
    return _(
        "Invoice %(number)s has been issued and can no longer be changed. "
        "Cancel it and create a corrected copy instead."
    ) % {"number": number}


@receiver(pre_save, sender=Invoice)
def guard_issued_invoice_content(
    sender,
    instance,
    update_fields=None,
    **kwargs,  # noqa: ARG001, vulture
):  # pylint: disable=unused-argument
    """Refuse changes to an issued invoice's content, and moving it back to draft.

    Checks the stored row, not the in-memory status, so the save that issues a
    draft (draft -> sent) may still carry its final content.
    """
    if not instance.pk or issued_invoice_writes_allowed():
        return
    stored = Invoice.objects.filter(pk=instance.pk).first()
    if stored is None or not stored.is_protected:
        return
    if instance.status == Invoice.Status.DRAFT:
        raise InvoiceLockedError(_locked_message(stored.invoice_number))

    fields = LOCKED_INVOICE_FIELDS
    if update_fields is not None:
        # update_fields may name "client" or "client_id"; only those get written.
        written = {name.removesuffix("_id") for name in update_fields}
        fields = tuple(f for f in fields if f.removesuffix("_id") in written)
    if any(getattr(instance, field) != getattr(stored, field) for field in fields):
        raise InvoiceLockedError(_locked_message(stored.invoice_number))


@receiver(pre_delete, sender=Invoice)
def guard_issued_invoice_delete(
    sender,
    instance,
    **kwargs,  # noqa: ARG001, vulture
):  # pylint: disable=unused-argument
    """Refuse deleting an issued invoice still inside its retention period."""
    if issued_invoice_writes_allowed():
        return
    stored = Invoice.objects.filter(pk=instance.pk).first()
    if stored is not None and stored.is_protected:
        raise InvoiceLockedError(
            _(
                "Invoice %(number)s has been issued and must be kept until the end of "
                "%(year)s. Cancel it instead of deleting it."
            )
            % {"number": stored.invoice_number, "year": stored.retention_end_year}
        )


def _raise_if_protected(invoice_ids) -> None:
    if issued_invoice_writes_allowed():
        return
    for invoice in Invoice.objects.filter(pk__in=invoice_ids).exclude(status=Invoice.Status.DRAFT):
        if invoice.is_protected:
            raise InvoiceLockedError(_locked_message(invoice.invoice_number))


@receiver(pre_save, sender=InvoiceItem)
def guard_items_of_issued_invoice(
    sender,
    instance,
    **kwargs,  # noqa: ARG001, vulture
):  # pylint: disable=unused-argument
    """Refuse adding or changing a line item on an issued invoice (or moving one off it)."""
    invoice_ids = {instance.invoice_id}
    if instance.pk:
        invoice_ids.update(
            InvoiceItem.objects.filter(pk=instance.pk).values_list("invoice_id", flat=True)
        )
    _raise_if_protected(invoice_ids)


@receiver(pre_delete, sender=InvoiceItem)
def guard_item_delete_of_issued_invoice(
    sender,
    instance,
    **kwargs,  # noqa: ARG001, vulture
):  # pylint: disable=unused-argument
    """Refuse removing a line item from an issued invoice still within retention."""
    _raise_if_protected({instance.invoice_id})


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


@receiver(pre_save, sender=Practice)
def delete_old_practice_image_on_replace(
    sender,
    instance,
    **kwargs,  # noqa: ARG001, vulture
):  # pylint: disable=unused-argument
    """Delete the old logo/signature file when it's replaced by a new upload."""
    if not instance.pk:
        return
    try:
        old = Practice.objects.get(pk=instance.pk)
    except Practice.DoesNotExist:
        return
    for field_name in ("logo", "signature"):
        old_file = getattr(old, field_name)
        new_file = getattr(instance, field_name)
        if old_file and old_file != new_file:
            old_file.delete(save=False)


@receiver(post_delete, sender=Practice)
def delete_practice_images_on_delete(
    sender,
    instance,
    **kwargs,  # noqa: ARG001, vulture
):  # pylint: disable=unused-argument
    """Delete logo/signature files when a Practice itself is deleted."""
    for field_name in ("logo", "signature"):
        file_field = getattr(instance, field_name)
        if file_field:
            file_field.delete(save=False)
