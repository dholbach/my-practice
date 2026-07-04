"""
Tests for practice management views.
"""

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import Practice, UserPractice
from ..tests.test_helpers import link_user_to_practice


def _make_practice(slug, name="Test Practice"):
    return Practice.objects.create(
        name=name,
        slug=slug,
        title="Test Practitioner",
        email="test@practice.example",
        city="Berlin",
    )


def _setup_client(user, practice=None):
    tc = TestClient()
    tc.login(username=user.username, password="testpass123")
    if practice:
        session = tc.session
        session["current_practice_slug"] = practice.slug
        session.save()
    return tc


class PracticeSwitchTest(TestCase):
    """Tests for practice_switch view."""

    def setUp(self):
        self.user = User.objects.create_user(username="switchuser", password="testpass123")
        self.practice1 = _make_practice("pswitch-1", "Practice One")
        self.practice2 = _make_practice("pswitch-2", "Practice Two")
        link_user_to_practice(self.user, self.practice1)
        link_user_to_practice(self.user, self.practice2)
        self.tc = _setup_client(self.user, self.practice1)

    def test_switch_sets_practice_in_session(self):
        self.tc.get(reverse("practice_switch", args=[self.practice2.slug]))
        session = self.tc.session
        self.assertEqual(session.get("current_practice_slug"), self.practice2.slug)

    def test_switch_redirects(self):
        response = self.tc.get(reverse("practice_switch", args=[self.practice2.slug]))
        self.assertEqual(response.status_code, 302)

    def test_switch_unknown_slug_redirects_with_error(self):
        response = self.tc.get(reverse("practice_switch", args=["no-such-practice"]))
        self.assertEqual(response.status_code, 302)

    def test_no_open_redirect_via_referer(self):
        """HTTP_REFERER with external host must not redirect off-site."""
        response = self.tc.get(
            reverse("practice_switch", args=[self.practice2.slug]),
            HTTP_REFERER="https://evil.example.com/steal",
        )
        location = response["Location"]
        # Must not redirect to an external domain
        self.assertFalse(location.startswith("https://evil.example.com"))


class PracticeSelectTest(TestCase):
    """Tests for practice_select view."""

    def setUp(self):
        self.user = User.objects.create_user(username="selectuser", password="testpass123")
        self.practice = _make_practice("pselect-1")
        link_user_to_practice(self.user, self.practice)
        self.tc = TestClient()
        self.tc.login(username="selectuser", password="testpass123")

    def test_single_practice_auto_redirects(self):
        """Single practice: auto-select and redirect to dashboard."""
        response = self.tc.get(reverse("practice_select"))
        self.assertEqual(response.status_code, 302)

    def test_multiple_practices_shows_form(self):
        practice2 = _make_practice("pselect-2", "Second Practice")
        link_user_to_practice(self.user, practice2)
        response = self.tc.get(reverse("practice_select"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/practice_select.html")


class PracticeManagementViewTest(TestCase):
    """Tests for PracticeManagementView."""

    def setUp(self):
        self.user = User.objects.create_user(username="mgmtuser", password="testpass123")
        self.practice = _make_practice("pmgmt-1")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)

    def test_get_lists_practices(self):
        response = self.tc.get(reverse("practice_management"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/practice_management.html")
        slugs = [p["practice"].slug for p in response.context["practices_with_ownership"]]
        self.assertIn("pmgmt-1", slugs)


class PracticeCreateViewTest(TestCase):
    """Tests for PracticeCreateView."""

    def setUp(self):
        self.user = User.objects.create_user(username="createpuser", password="testpass123")
        self.tc = TestClient()
        self.tc.login(username="createpuser", password="testpass123")

    def test_get_renders_form(self):
        response = self.tc.get(reverse("practice_create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/practice_form.html")

    def test_post_creates_practice_and_user_practice(self):
        data = {
            "name": "New Practice",
            "short_title": "Therapie",
            "title": "Dr. Musterfrau",
            "subtitle_de": "",
            "subtitle_en": "",
            "street": "Musterstr. 1",
            "postal_code": "10115",
            "city": "Berlin",
            "country": "Deutschland",
            "email": "neu@praxis.example",
            "email_from_name": "Dr. Musterfrau",
            "website": "https://praxis.example",
            "phone": "",
            "bank_name": "Musterbank",
            "iban": "DE89370400440532013000",
            "bic": "COBADEFFXXX",
            "tax_id": "123/456/78901",
        }
        response = self.tc.post(reverse("practice_create"), data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Practice.objects.filter(name="New Practice").exists())
        practice = Practice.objects.get(name="New Practice")
        self.assertTrue(
            UserPractice.objects.filter(user=self.user, practice=practice, is_owner=True).exists()
        )


class PracticeUpdateViewTest(TestCase):
    """Tests for PracticeUpdateView."""

    def setUp(self):
        self.owner = User.objects.create_user(username="ownerpuser", password="testpass123")
        self.other = User.objects.create_user(username="otherpuser", password="testpass123")
        self.practice = _make_practice("pupdate-1")
        link_user_to_practice(self.owner, self.practice, is_owner=True)
        link_user_to_practice(self.other, self.practice, is_owner=False)
        self.tc_owner = _setup_client(self.owner, self.practice)
        self.tc_other = _setup_client(self.other, self.practice)

    def test_owner_can_get_edit_form(self):
        response = self.tc_owner.get(reverse("practice_edit", args=[self.practice.slug]))
        self.assertEqual(response.status_code, 200)

    def test_non_owner_is_redirected(self):
        response = self.tc_other.get(reverse("practice_edit", args=[self.practice.slug]))
        self.assertEqual(response.status_code, 302)

    def test_owner_can_post_update(self):
        data = {
            # Capacity formset management form (empty — no periods being edited)
            "capacity_periods-TOTAL_FORMS": "0",
            "capacity_periods-INITIAL_FORMS": "0",
            "capacity_periods-MIN_NUM_FORMS": "0",
            "capacity_periods-MAX_NUM_FORMS": "1000",
            "name": "Renamed Practice",
            "short_title": "Therapie",
            "title": "Dr. Mustermann",
            "subtitle_de": "praxis",
            "subtitle_en": "practice",
            "street": "Musterstr. 2",
            "postal_code": "20095",
            "city": "Hamburg",
            "country": "Deutschland",
            "email": "renamed@praxis.example",
            "email_from_name": "Dr. Mustermann",
            "website": "https://renamed.example",
            "booking_url": "",
            "phone": "",
            "bank_name": "Musterbank",
            "iban": "DE89370400440532013000",
            "bic": "COBADEFFXXX",
            "tax_id": "123/456/789",
            "is_active": True,
            "is_kleinunternehmer": False,
            "kleinunternehmer_text_de": "§ 19 UStG.",
            "kleinunternehmer_text_en": "VAT exempt.",
            "vat_exempt_text_de": "§ 4 Nr. 14 UStG.",
            "vat_exempt_text_en": "VAT exempt.",
            "memberships_de": "DGSF",
            "memberships_en": "DGSF",
            "payment_terms_days": 14,
            "payment_terms_text_de": "Zahlung innerhalb von 14 Tagen.",
            "payment_terms_text_en": "Payment within 14 days.",
            "commute_distance_km": "",
        }
        response = self.tc_owner.post(reverse("practice_edit", args=[self.practice.slug]), data)
        self.assertEqual(response.status_code, 302)
        self.practice.refresh_from_db()
        self.assertEqual(self.practice.name, "Renamed Practice")


class PracticeDeleteViewTest(TestCase):
    """Tests for PracticeDeleteView — soft-delete sets is_active=False."""

    def setUp(self):
        self.user = User.objects.create_user(username="delpuser", password="testpass123")
        self.practice = _make_practice("pdelete-1")
        link_user_to_practice(self.user, self.practice, is_owner=True)
        self.tc = _setup_client(self.user, self.practice)

    def test_get_shows_confirmation(self):
        response = self.tc.get(reverse("practice_delete", args=[self.practice.slug]))
        self.assertEqual(response.status_code, 200)

    def test_post_soft_deletes_practice(self):
        response = self.tc.post(reverse("practice_delete", args=[self.practice.slug]))
        self.assertEqual(response.status_code, 302)
        self.practice.refresh_from_db()
        self.assertFalse(self.practice.is_active)

    def test_non_owner_cannot_delete(self):
        other = User.objects.create_user(username="nondelpuser", password="testpass123")
        link_user_to_practice(other, self.practice, is_owner=False)
        tc_other = _setup_client(other, self.practice)
        response = tc_other.post(reverse("practice_delete", args=[self.practice.slug]))
        self.assertEqual(response.status_code, 302)
        self.practice.refresh_from_db()
        self.assertTrue(self.practice.is_active)
