"""
Close lapsed inquiries and anonymise closed ones past the retention period.

Two passes, both across every practice:

1. Lapse — an open inquiry whose newest milestone is more than
   INQUIRY_LAPSE_DAYS old gets status LAPSED. Its decision date stays empty:
   nothing was decided, and a made-up date would skew the time-in-stage
   averages on the inquiry page.
2. Anonymise — a closed inquiry that never became a client, whose last contact
   is more than INQUIRY_RETENTION_DAYS ago, has its name, contact details and
   notes wiped. Date, source, status, language and milestones stay, so the
   inquiry statistics keep working. Onboarded inquiries are left alone: the
   person's data now lives in the Client record under its own retention rules.

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

        to_lapse = []
        for inquiry in ClientInquiry.objects.open():
            step_date, _field = inquiry.last_step()
            if (today - step_date).days > INQUIRY_LAPSE_DAYS:
                to_lapse.append((inquiry, (today - step_date).days))

        # Lapsing happens first, so an inquiry can lapse and be anonymised in the
        # same run — both thresholds count from the same last step.
        lapsing_ids = {inquiry.pk for inquiry, _days in to_lapse}
        to_anonymise = []
        candidates = ClientInquiry.objects.filter(
            anonymised_at__isnull=True, converted_client__isnull=True
        ).exclude(status=InquiryStatus.CONVERTED)
        for inquiry in candidates:
            if inquiry.status not in CLOSED_INQUIRY_STATUSES and inquiry.pk not in lapsing_ids:
                continue
            step_date, _field = inquiry.last_step()
            if (today - step_date).days > INQUIRY_RETENTION_DAYS:
                to_anonymise.append((inquiry, (today - step_date).days))

        for inquiry, days in to_lapse:
            self.stdout.write(
                f"{prefix}lapse     #{inquiry.pk} ({inquiry.status}, {days} days since last step)"
            )
        for inquiry, days in to_anonymise:
            self.stdout.write(
                f"{prefix}anonymise #{inquiry.pk} ({inquiry.status}, {days} days since last contact)"
            )

        if apply:
            with transaction.atomic():
                for inquiry, _days in to_lapse:
                    inquiry.status = InquiryStatus.LAPSED
                    inquiry.save(update_fields=["status", "updated_at"])
                for inquiry, _days in to_anonymise:
                    inquiry.anonymise()
            logger.info(
                "tidy_inquiries: lapsed %d, anonymised %d", len(to_lapse), len(to_anonymise)
            )

        verb = "" if apply else "would be "
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(to_lapse)} {verb}lapsed, {len(to_anonymise)} {verb}anonymised."
            )
        )
