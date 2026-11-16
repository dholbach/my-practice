"""``Client.mark_onboarding_step``: the one place an onboarding date is set or reset."""

from datetime import date

from django.test import TestCase

from ..models import ClientTag
from ..models.client import INCOMPLETE_INTAKE_TAG_SLUG
from .test_helpers import create_test_client, create_test_practice


class MarkOnboardingStepTests(TestCase):
    def setUp(self):
        self.practice = create_test_practice()
        self.client_record = create_test_client(self.practice)

    def test_sets_and_resets_the_step_date(self):
        self.client_record.mark_onboarding_step("contract", date(2026, 3, 1))
        self.client_record.refresh_from_db()
        self.assertEqual(self.client_record.contract_signed_date, date(2026, 3, 1))

        self.client_record.mark_onboarding_step("contract", None)
        self.client_record.refresh_from_db()
        self.assertIsNone(self.client_record.contract_signed_date)

    def test_only_if_unset_keeps_an_existing_date(self):
        self.client_record.mark_onboarding_step("intake", date(2026, 3, 1))

        changed = self.client_record.mark_onboarding_step(
            "intake", date(2026, 4, 1), only_if_unset=True
        )

        self.assertFalse(changed)
        self.client_record.refresh_from_db()
        self.assertEqual(self.client_record.intake_sent_date, date(2026, 3, 1))

    def test_completing_drops_the_incomplete_intake_tag_but_resetting_does_not(self):
        tag = ClientTag.objects.create(
            name=INCOMPLETE_INTAKE_TAG_SLUG, slug=INCOMPLETE_INTAKE_TAG_SLUG
        )
        self.client_record.tags.add(tag)

        self.client_record.mark_onboarding_step("complete", None)
        self.assertEqual(list(self.client_record.tags.all()), [tag])

        self.client_record.mark_onboarding_step("complete", date(2026, 3, 1))
        self.assertEqual(list(self.client_record.tags.all()), [])
