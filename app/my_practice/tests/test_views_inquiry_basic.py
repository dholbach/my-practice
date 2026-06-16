"""
Tests for inquiry views.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import ClientInquiry, InquiryStatus, Practice
from ..tests.test_helpers import link_user_to_practice


def _make_practice(slug):
    return Practice.objects.create(
        name="Inquiry Practice",
        slug=slug,
        title="Test Practitioner",
        email="inquiry@practice.example",
        city="Berlin",
    )


def _setup_client(user, practice):
    tc = TestClient()
    tc.login(username=user.username, password="testpass123")
    session = tc.session
    session["current_practice_slug"] = practice.slug
    session.save()
    return tc


def _make_inquiry(practice, name="Anna Schmidt", status=InquiryStatus.NEW):
    return ClientInquiry.objects.create(
        practice=practice,
        full_name=name,
        email="anna@example.com",
        source="website",
        status=status,
        inquiry_date=date.today(),
    )


class InquiryListViewTest(TestCase):
    """Tests for InquiryListView."""

    def setUp(self):
        self.practice = _make_practice("inq-list-1")
        self.user = User.objects.create_user(username="inquser", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        _make_inquiry(self.practice, "Anna Schmidt", InquiryStatus.NEW)
        _make_inquiry(self.practice, "Max Mustermann", InquiryStatus.DECLINED)

    def test_get_renders(self):
        response = self.tc.get(reverse("inquiry_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/inquiry_list.html")

    def test_default_hides_closed(self):
        response = self.tc.get(reverse("inquiry_list"))
        names = [i.full_name for i in response.context["inquiries"]]
        self.assertIn("Anna Schmidt", names)
        self.assertNotIn("Max Mustermann", names)

    def test_status_filter(self):
        response = self.tc.get(reverse("inquiry_list") + "?status=declined")
        names = [i.full_name for i in response.context["inquiries"]]
        self.assertIn("Max Mustermann", names)

    def test_show_closed_param(self):
        response = self.tc.get(reverse("inquiry_list") + "?show_closed=1")
        names = [i.full_name for i in response.context["inquiries"]]
        self.assertIn("Max Mustermann", names)


class InquiryCreateViewTest(TestCase):
    """Tests for InquiryCreateView."""

    def setUp(self):
        self.practice = _make_practice("inq-create-1")
        self.user = User.objects.create_user(username="inquser2", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)

    def test_get_renders(self):
        response = self.tc.get(reverse("inquiry_create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/inquiry_form.html")

    def test_post_valid_creates_inquiry(self):
        data = {
            "full_name": "Maria Musterfrau",
            "email": "maria@example.com",
            "source": "referral",
            "language": "de",
            "status": "new",
            "inquiry_date": date.today().isoformat(),
        }
        response = self.tc.post(reverse("inquiry_create"), data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ClientInquiry.objects.filter(full_name="Maria Musterfrau").exists())

    def test_post_missing_name_fails(self):
        data = {
            "full_name": "",
            "source": "website",
            "status": "new",
            "inquiry_date": date.today().isoformat(),
        }
        response = self.tc.post(reverse("inquiry_create"), data)
        self.assertEqual(response.status_code, 200)


class InquiryUpdateViewTest(TestCase):
    """Tests for InquiryUpdateView."""

    def setUp(self):
        self.practice = _make_practice("inq-update-1")
        self.user = User.objects.create_user(username="inquser3", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        self.inquiry = _make_inquiry(self.practice, "Anna Schmidt")

    def test_get_renders_with_data(self):
        response = self.tc.get(reverse("inquiry_edit", args=[self.inquiry.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Anna Schmidt")

    def test_post_updates_inquiry(self):
        data = {
            "full_name": "Anna Schmidt Updated",
            "email": "anna@example.com",
            "source": "website",
            "language": "de",
            "status": "contacted",
            "inquiry_date": date.today().isoformat(),
        }
        response = self.tc.post(reverse("inquiry_edit", args=[self.inquiry.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.inquiry.refresh_from_db()
        self.assertEqual(self.inquiry.full_name, "Anna Schmidt Updated")
        self.assertEqual(self.inquiry.status, "contacted")

    def test_nonexistent_returns_404(self):
        response = self.tc.get(reverse("inquiry_edit", args=[99999]))
        self.assertEqual(response.status_code, 404)


class InquiryDeleteViewTest(TestCase):
    """Tests for InquiryDeleteView."""

    def setUp(self):
        self.practice = _make_practice("inq-delete-1")
        self.user = User.objects.create_user(username="inquser4", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        self.inquiry = _make_inquiry(self.practice, "To Delete Inquiry")

    def test_get_shows_confirmation(self):
        response = self.tc.get(reverse("inquiry_delete", args=[self.inquiry.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_deletes_inquiry(self):
        pk = self.inquiry.pk
        response = self.tc.post(reverse("inquiry_delete", args=[pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ClientInquiry.objects.filter(pk=pk).exists())


class InquiryConvertViewTest(TestCase):
    """Tests for InquiryConvertView."""

    def setUp(self):
        self.practice = _make_practice("inq-convert-1")
        self.user = User.objects.create_user(username="inquser5", password="testpass123")
        link_user_to_practice(self.user, self.practice)
        self.tc = _setup_client(self.user, self.practice)
        self.inquiry = _make_inquiry(self.practice, "Convert Me", InquiryStatus.IN_INTAKE)

    def test_get_shows_form(self):
        response = self.tc.get(reverse("inquiry_convert", args=[self.inquiry.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/inquiry_convert_confirm.html")

    def test_post_valid_creates_client(self):
        data = {
            "client_code": "CM-1",
            "default_hourly_rate": "90.00",
        }
        response = self.tc.post(reverse("inquiry_convert", args=[self.inquiry.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.inquiry.refresh_from_db()
        self.assertEqual(self.inquiry.status, InquiryStatus.CONVERTED)
        self.assertIsNotNone(self.inquiry.converted_client)

    def test_post_duplicate_code_fails(self):
        from ..models import Client

        Client.objects.create(
            practice=self.practice,
            client_code="DUP-1",
            full_name="Existing Client",
            hourly_rate_60=Decimal("80.00"),
        )
        data = {
            "client_code": "DUP-1",
            "default_hourly_rate": "90.00",
        }
        response = self.tc.post(reverse("inquiry_convert", args=[self.inquiry.pk]), data)
        self.assertEqual(response.status_code, 200)  # Form error
