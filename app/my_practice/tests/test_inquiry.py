"""
Tests for ClientInquiry model and views (P-031).
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from my_practice.models import (
    Client,
    ClientInquiry,
    InquirySource,
    InquiryStatus,
    Practice,
    UserPractice,
)


def _make_user_and_practice(username="testuser"):
    user = User.objects.create_user(username=username, password="testpass")
    practice = Practice.objects.create(
        name="Test Praxis",
        slug=f"test-praxis-{username}",
        email=f"{username}@example.com",
    )
    UserPractice.objects.create(user=user, practice=practice, is_owner=True)
    return user, practice


def _make_inquiry(practice, **kwargs):
    defaults = {
        "full_name": "Max Mustermann",
        "email": "max@example.com",
        "source": InquirySource.WEBSITE,
        "status": InquiryStatus.NEW,
        "inquiry_date": date(2026, 3, 1),
    }
    defaults.update(kwargs)
    return ClientInquiry.objects.create(practice=practice, **defaults)


class InquiryModelTestCase(TestCase):
    """Unit tests for ClientInquiry model."""

    def setUp(self):
        _, self.practice = _make_user_and_practice()

    def test_str(self):
        inquiry = _make_inquiry(self.practice, full_name="Anna Schmidt")
        self.assertIn("Anna Schmidt", str(inquiry))
        self.assertIn("Neu", str(inquiry))

    def test_is_closed_converted(self):
        inquiry = _make_inquiry(self.practice, status=InquiryStatus.CONVERTED)
        self.assertTrue(inquiry.is_closed())

    def test_is_closed_declined(self):
        inquiry = _make_inquiry(self.practice, status=InquiryStatus.DECLINED)
        self.assertTrue(inquiry.is_closed())

    def test_is_closed_unreachable(self):
        inquiry = _make_inquiry(self.practice, status=InquiryStatus.UNREACHABLE)
        self.assertTrue(inquiry.is_closed())

    def test_not_closed_when_open(self):
        for status in (
            InquiryStatus.NEW,
            InquiryStatus.CONTACTED,
            InquiryStatus.INTRO_MEETING,
            InquiryStatus.WAITLIST,
            InquiryStatus.IN_INTAKE,
        ):
            inquiry = _make_inquiry(self.practice, status=status)
            self.assertFalse(inquiry.is_closed(), msg=f"Expected open for status={status}")

    def test_open_queryset(self):
        _make_inquiry(self.practice, status=InquiryStatus.NEW)
        _make_inquiry(self.practice, status=InquiryStatus.CONVERTED)
        _make_inquiry(self.practice, status=InquiryStatus.DECLINED)
        open_qs = ClientInquiry.objects.for_practice(self.practice).open()
        self.assertEqual(open_qs.count(), 1)

    def test_practice_scoping(self):
        _, other_practice = _make_user_and_practice(username="other")
        _make_inquiry(self.practice)
        _make_inquiry(other_practice)
        qs = ClientInquiry.objects.for_practice(self.practice)
        self.assertEqual(qs.count(), 1)

    def test_timestamps(self):
        inquiry = _make_inquiry(self.practice)
        self.assertIsNotNone(inquiry.created_at)
        self.assertIsNotNone(inquiry.updated_at)


class InquiryListViewTestCase(TestCase):
    """Tests for InquiryListView."""

    def setUp(self):
        self.user, self.practice = _make_user_and_practice()
        self.client_obj = self.client  # test client (HTTP)
        self.client_obj.login(username="testuser", password="testpass")
        # Set the practice via session
        session = self.client_obj.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

    def test_list_requires_login(self):
        self.client_obj.logout()
        resp = self.client_obj.get(reverse("inquiry_list"))
        self.assertNotEqual(resp.status_code, 200)

    def test_list_shows_own_inquiries(self):
        _make_inquiry(self.practice, full_name="Max Mustermann")
        resp = self.client_obj.get(reverse("inquiry_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Max Mustermann")

    def test_list_isolates_other_practice(self):
        _, other_practice = _make_user_and_practice(username="other")
        _make_inquiry(other_practice, full_name="Anna Schmidt")
        resp = self.client_obj.get(reverse("inquiry_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Anna Schmidt")

    def test_status_filter(self):
        _make_inquiry(self.practice, status=InquiryStatus.NEW, full_name="Neu Person")
        _make_inquiry(self.practice, status=InquiryStatus.WAITLIST, full_name="Warte Person")
        resp = self.client_obj.get(reverse("inquiry_list") + "?status=waitlist")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Warte Person")
        self.assertNotContains(resp, "Neu Person")

    def test_source_filter(self):
        _make_inquiry(self.practice, source=InquirySource.GOOGLE_ADS, full_name="Ads Person")
        _make_inquiry(self.practice, source=InquirySource.REFERRAL, full_name="Empfehlung Person")
        resp = self.client_obj.get(reverse("inquiry_list") + "?source=referral")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Empfehlung Person")
        self.assertNotContains(resp, "Ads Person")


class InquiryCRUDViewTestCase(TestCase):
    """Tests for create, update, delete views."""

    def setUp(self):
        self.user, self.practice = _make_user_and_practice()
        self.http = self.client
        self.http.login(username="testuser", password="testpass")
        session = self.http.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

    def test_create_inquiry(self):
        self.http.post(
            reverse("inquiry_create"),
            {
                "full_name": "Test Person",
                "email": "test@example.com",
                "phone": "",
                "source": "website",
                "language": "de",
                "status": "new",
                "inquiry_date": "2026-03-01",
                "notes": "",
            },
        )
        self.assertEqual(ClientInquiry.objects.filter(practice=self.practice).count(), 1)
        inquiry = ClientInquiry.objects.get(practice=self.practice)
        self.assertEqual(inquiry.full_name, "Test Person")
        self.assertEqual(inquiry.source, InquirySource.WEBSITE)

    def test_update_inquiry(self):
        inquiry = _make_inquiry(self.practice)
        self.http.post(
            reverse("inquiry_edit", kwargs={"pk": inquiry.pk}),
            {
                "full_name": inquiry.full_name,
                "email": inquiry.email,
                "phone": "",
                "source": "referral",
                "language": "de",
                "status": "contacted",
                "inquiry_date": "2026-03-01",
                "notes": "Updated",
            },
        )
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, InquiryStatus.CONTACTED)
        self.assertEqual(inquiry.source, InquirySource.REFERRAL)

    def test_delete_inquiry(self):
        inquiry = _make_inquiry(self.practice)
        self.http.post(reverse("inquiry_delete", kwargs={"pk": inquiry.pk}))
        self.assertFalse(ClientInquiry.objects.filter(pk=inquiry.pk).exists())

    def test_delete_scoped_to_practice(self):
        """Cannot delete another practice's inquiry."""
        _, other_practice = _make_user_and_practice(username="other2")
        other_inquiry = _make_inquiry(other_practice)
        resp = self.http.post(reverse("inquiry_delete", kwargs={"pk": other_inquiry.pk}))
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(ClientInquiry.objects.filter(pk=other_inquiry.pk).exists())


class InquiryConvertViewTestCase(TestCase):
    """Tests for InquiryConvertView — converting an inquiry to a Client."""

    def setUp(self):
        self.user, self.practice = _make_user_and_practice()
        self.http = self.client
        self.http.login(username="testuser", password="testpass")
        session = self.http.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

    def test_convert_creates_client(self):
        inquiry = _make_inquiry(
            self.practice,
            full_name="Maria Musterfrau",
            email="maria@example.com",
            phone="+49 30 12345",
        )
        self.http.post(
            reverse("inquiry_convert", kwargs={"pk": inquiry.pk}),
            {
                "client_code": "MM-1",
                "first_seen_date": "2026-03-15",
                "default_hourly_rate": "90.00",
            },
        )
        # Client was created
        self.assertTrue(Client.objects.filter(client_code="MM-1").exists())
        client = Client.objects.get(client_code="MM-1")
        self.assertEqual(client.full_name, "Maria Musterfrau")
        self.assertEqual(client.email, "maria@example.com")
        self.assertEqual(client.practice, self.practice)

    def test_convert_links_inquiry_to_client(self):
        inquiry = _make_inquiry(self.practice, full_name="Test Convert")
        self.http.post(
            reverse("inquiry_convert", kwargs={"pk": inquiry.pk}),
            {
                "client_code": "TC-1",
                "first_seen_date": "",
                "default_hourly_rate": "90.00",
            },
        )
        inquiry.refresh_from_db()
        self.assertIsNotNone(inquiry.converted_client)
        self.assertEqual(inquiry.status, InquiryStatus.CONVERTED)

    def test_convert_redirects_to_client_detail(self):
        inquiry = _make_inquiry(self.practice)
        resp = self.http.post(
            reverse("inquiry_convert", kwargs={"pk": inquiry.pk}),
            {
                "client_code": "MX-9",
                "first_seen_date": "",
                "default_hourly_rate": "90.00",
            },
        )
        client = Client.objects.get(client_code="MX-9")
        self.assertRedirects(resp, reverse("client_detail", kwargs={"pk": client.pk}))

    def test_convert_duplicate_client_code_shows_error(self):
        inquiry = _make_inquiry(self.practice)
        Client.objects.create(
            practice=self.practice,
            full_name="Existing Client",
            email="existing@example.com",
            client_code="DUP-1",
        )
        resp = self.http.post(
            reverse("inquiry_convert", kwargs={"pk": inquiry.pk}),
            {
                "client_code": "DUP-1",
                "first_seen_date": "",
                "default_hourly_rate": "90.00",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            Client.objects.filter(client_code="DUP-1", full_name="Max Mustermann").exists()
        )

    def test_convert_scoped_to_practice(self):
        """Cannot convert another practice's inquiry."""
        _, other_practice = _make_user_and_practice(username="other3")
        other_inquiry = _make_inquiry(other_practice)
        resp = self.http.post(
            reverse("inquiry_convert", kwargs={"pk": other_inquiry.pk}),
            {
                "client_code": "XX-1",
                "first_seen_date": "",
                "default_hourly_rate": "90.00",
            },
        )
        self.assertEqual(resp.status_code, 404)
