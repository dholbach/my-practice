"""
Close lapsed inquiries and anonymise closed ones past the retention period.

Two passes, both across every practice:

1. Lapse — an open inquiry whose newest milestone is more than
   INQUIRY_LAPSE_DAYS old gets status LAPSED. Its decision date stays empty:
   nothing was decided, and a made-up date would skew the time-in-stage
   averages on the inquiry page.
2. Anonymise — a closed inquiry not linked to a client, whose last contact is
   more than INQUIRY_RETENTION_DAYS ago, has its name, contact details and
   notes wiped. Date, source, status, language and milestones stay, so the
   inquiry statistics keep working. Inquiries linked to a client are left
   alone: the person's data lives in the Client record under its own retention
   rules. A "converted" inquiry without one — marked converted by hand, or
   left behind by a client deleted before the client-delete signal existed —
   follows the normal retention period.

Dry run by default; --apply makes the changes. Anonymising cannot be undone.
Output names inquiries by id only — never by name.
"""

import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from ...models import (
    CLOSED_INQUIRY_STATUSES,
    INQUIRY_LAPSE_DAYS,
    INQUIRY_RETENTION_DAYS,
    ClientInquiry,
    InquiryStatus,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        f"Close inquiries with no step for {INQUIRY_LAPSE_DAYS} days as lapsed, and anonymise "
        f"closed non-client inquiries {INQUIRY_RETENTION_DAYS} days after the last contact. "
        "Dry run unless --apply is given."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Make the changes (default: only list what would change)",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        today = timezone.localdate()
        prefix = "" if apply else "[dry-run] "

        to_lapse = self._inquiries_to_lapse(today)
        to_anonymise = self._inquiries_to_anonymise(today, {i.pk for i, _days in to_lapse})

        for inquiry, days in to_lapse:
            self.stdout.write(
                f"{prefix}lapse     #{inquiry.pk} ({inquiry.status}, {days} days since last step)"
            )
        for inquiry, days in to_anonymise:
            self.stdout.write(
                f"{prefix}anonymise #{inquiry.pk} ({inquiry.status}, {days} days since last contact)"
            )

        if apply:
            self._apply(to_lapse, to_anonymise)

        verb = "" if apply else "would be "
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(to_lapse)} {verb}lapsed, {len(to_anonymise)} {verb}anonymised."
            )
        )

    @staticmethod
    def _inquiries_to_lapse(today) -> list[tuple[ClientInquiry, int]]:
        """Open inquiries whose newest step is older than INQUIRY_LAPSE_DAYS, with that age."""
        found = []
        for inquiry in ClientInquiry.objects.open():
            step_date, _field = inquiry.last_step()
            if (today - step_date).days > INQUIRY_LAPSE_DAYS:
                found.append((inquiry, (today - step_date).days))
        return found

    @staticmethod
    def _inquiries_to_anonymise(today, lapsing_ids: set[int]) -> list[tuple[ClientInquiry, int]]:
        """Closed (or about to lapse) inquiries past retention that no client record covers.

        Lapsing happens first, so an inquiry can lapse and be anonymised in the
        same run — both thresholds count from the same last step.
        """
        found = []
        candidates = ClientInquiry.objects.filter(
            anonymised_at__isnull=True, converted_client__isnull=True
        )
        for inquiry in candidates:
            if inquiry.status not in CLOSED_INQUIRY_STATUSES and inquiry.pk not in lapsing_ids:
                continue
            step_date, _field = inquiry.last_step()
            if (today - step_date).days > INQUIRY_RETENTION_DAYS:
                found.append((inquiry, (today - step_date).days))
        return found

    @staticmethod
    def _apply(to_lapse, to_anonymise) -> None:
        """Lapse and anonymise in one transaction: an error leaves every inquiry as it was."""
        with transaction.atomic():
            for inquiry, _days in to_lapse:
                inquiry.status = InquiryStatus.LAPSED
                inquiry.save(update_fields=["status", "updated_at"])
            for inquiry, _days in to_anonymise:
                inquiry.anonymise()
        logger.info("tidy_inquiries: lapsed %d, anonymised %d", len(to_lapse), len(to_anonymise))
