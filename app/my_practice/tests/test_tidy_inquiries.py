"""Tests for the tidy_inquiries command: lapsing stale inquiries, anonymising old closed ones."""

from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from my_practice.models import (
    Client,
    ClientInquiry,
    InquirySource,
    InquiryStatus,
    Practice,
)

TODAY = date(2026, 10, 21)


class TidyInquiriesTestCase(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Praxis", slug="test-praxis", email="mail@example.com"
        )

    def _inquiry(self, days_ago, status=InquiryStatus.CONTACTED, **kwargs):
        defaults = {
            "full_name": "Max Mustermann",
            "email": "max@example.com",
            "phone": "+49 123 456789",
            "notes": "Some notes",
            "initial_contact_notes": "First call",
            "source": InquirySource.WEBSITE,
            "status": status,
            "inquiry_date": TODAY - timedelta(days=days_ago),
        }
        defaults.update(kwargs)
        return ClientInquiry.objects.create(practice=self.practice, **defaults)

    def _run(self, *args):
        out = StringIO()
        with patch("django.utils.timezone.localdate", return_value=TODAY):
            call_command("tidy_inquiries", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        inquiry = self._inquiry(300)
        output = self._run()
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, InquiryStatus.CONTACTED)
        self.assertEqual(inquiry.full_name, "Max Mustermann")
        self.assertIn("1 would be lapsed, 1 would be anonymised", output)
        self.assertNotIn("Mustermann", output)

    def test_lapses_after_threshold_counting_from_latest_step(self):
        stale = self._inquiry(61)
        fresh = self._inquiry(60)
        recently_contacted = self._inquiry(100, contacted_date=TODAY - timedelta(days=10))
        intro_booked = self._inquiry(
            90, status=InquiryStatus.INTRO_MEETING, intro_date=TODAY + timedelta(days=3)
        )
        self._run("--apply")
        for inquiry, expected in [
            (stale, InquiryStatus.LAPSED),
            (fresh, InquiryStatus.CONTACTED),
            (recently_contacted, InquiryStatus.CONTACTED),
            (intro_booked, InquiryStatus.INTRO_MEETING),
        ]:
            inquiry.refresh_from_db()
            self.assertEqual(inquiry.status, expected)
        stale.refresh_from_db()
        self.assertIsNone(stale.decision_date)

    def test_anonymises_closed_inquiries_past_retention(self):
        old = self._inquiry(181, status=InquiryStatus.DECLINED)
        recent = self._inquiry(179, status=InquiryStatus.DECLINED)
        self._run("--apply")
        old.refresh_from_db()
        recent.refresh_from_db()
        for field in ("full_name", "email", "phone", "notes", "initial_contact_notes"):
            self.assertEqual(getattr(old, field), "", field)
        self.assertIsNotNone(old.anonymised_at)
        # Statistical fields survive.
        self.assertEqual(old.status, InquiryStatus.DECLINED)
        self.assertEqual(old.source, InquirySource.WEBSITE)
        self.assertEqual(old.inquiry_date, TODAY - timedelta(days=181))
        self.assertEqual(recent.full_name, "Max Mustermann")
        self.assertIsNone(recent.anonymised_at)

    def test_lapse_and_anonymise_in_one_run_keeps_lapsed_status(self):
        inquiry = self._inquiry(200)
        self._run("--apply")
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, InquiryStatus.LAPSED)
        self.assertEqual(inquiry.full_name, "")

    def test_onboarded_inquiries_are_never_anonymised(self):
        client = Client.objects.create(
            practice=self.practice, client_code="XX-1", full_name="Max Mustermann"
        )
        inquiry = self._inquiry(400, status=InquiryStatus.CONVERTED, converted_client=client)
        self._run("--apply")
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.full_name, "Max Mustermann")
        self.assertEqual(inquiry.status, InquiryStatus.CONVERTED)

    def test_second_run_is_a_no_op(self):
        self._inquiry(300)
        self._run("--apply")
        self.assertIn("0 lapsed, 0 anonymised", self._run("--apply"))
