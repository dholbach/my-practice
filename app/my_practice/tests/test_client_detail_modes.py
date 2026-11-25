"""The client page's Clinical and Admin modes (P-006 PR 3a): which section holds what."""

from datetime import date

from django.test import override_settings
from django.urls import reverse

from .test_clinical import TEST_FERNET_KEY, ClinicalTestBase


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class ClientDetailModesTests(ClinicalTestBase):
    def _html(self):
        response = self.http.get(reverse("client_detail", kwargs={"pk": self.client_obj.pk}))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def _sections(self, html):
        """The overview, protocol and admin sections' HTML, in page order."""
        overview_start = html.index('id="ptab-profil"')
        protocol_start = html.index('id="ptab-protokoll"')
        admin_start = html.index('id="ptab-abrechnung"')
        self.assertLess(overview_start, protocol_start)
        self.assertLess(protocol_start, admin_start)
        return (
            html[overview_start:protocol_start],
            html[protocol_start:admin_start],
            html[admin_start:],
        )

    def test_two_mode_buttons_and_no_protocol_tab(self):
        html = self._html()
        self.assertIn('data-tab="profil" data-mode="clinical"', html)
        self.assertIn('data-tab="abrechnung" data-mode="admin"', html)
        self.assertNotIn('data-tab="protokoll"', html)

    def test_sections_belong_to_their_mode(self):
        overview, protocol, admin = self._sections(self._html())
        self.assertIn('data-mode="clinical"', overview[:200])
        self.assertRegex(protocol[:400], r'data-mode="clinical"\s+data-scroll-on-open')
        self.assertIn('data-mode="admin"', admin[:200])

    def test_clinical_mode_is_shown_by_default_both_sections(self):
        overview, protocol, admin = self._sections(self._html())
        self.assertIn("page-tab-active", overview[:200])
        self.assertIn("page-tab-active", protocol[:200])
        self.assertNotIn("page-tab-active", admin[:200])

    def test_clinical_page_has_for_next_time_then_case_formulation_then_the_protocol(self):
        html = self._html()
        overview, protocol, _admin = self._sections(html)
        self.assertLess(
            overview.index('id="for-next-time"'), overview.index('id="client-profile-form"')
        )
        self.assertIn("cn-supervision-section", protocol)

    def test_contact_onboarding_and_billing_are_admin_only(self):
        overview, protocol, admin = self._sections(self._html())
        for marker in ('class="contact-grid"', 'id="onboarding"', "send_payment_reminder"):
            self.assertNotIn(marker, overview, marker)
            self.assertNotIn(marker, protocol, marker)
        self.assertIn('class="contact-grid"', admin)
        self.assertIn('id="onboarding"', admin)
        self.assertIn('class="client-actions', admin)

    def test_documents_follow_the_protocol_in_the_clinical_mode(self):
        overview, protocol, admin = self._sections(self._html())
        self.assertIn('id="client-documents"', protocol)
        self.assertNotIn('id="client-documents"', overview)
        self.assertNotIn('id="client-documents"', admin)

    def test_the_old_recent_sessions_card_is_gone(self):
        overview, _protocol, _admin = self._sections(self._html())
        self.assertNotIn("cockpit-session", overview)
        self.assertNotIn("cockpit-split", overview)

    def test_intake_hint_shows_while_onboarding_is_open_and_links_to_admin(self):
        self.client_obj.intake_sent_date = date(2026, 3, 1)
        self.client_obj.save()
        overview, _protocol, _admin = self._sections(self._html())
        self.assertIn('href="#onboarding" data-page-tab="abrechnung"', overview)

    def test_intake_hint_is_gone_once_onboarding_is_complete(self):
        self.client_obj.onboarding_complete_date = date(2026, 3, 10)
        self.client_obj.save()
        overview, _protocol, _admin = self._sections(self._html())
        self.assertNotIn('href="#onboarding"', overview)

    def test_old_hash_links_still_have_a_target(self):
        """Redirects elsewhere in the app end in #ptab-profil / #ptab-protokoll / #ptab-abrechnung."""
        html = self._html()
        for name in ("profil", "protokoll", "abrechnung"):
            self.assertIn(f'id="ptab-{name}"', html)
