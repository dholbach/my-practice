"""
Tests for time-off views (CRUD + heads-up email notice).
"""

import logging
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import Client, Practice, Session, TimeOff, UserPractice


class TimeOffCrudViewTest(TestCase):
    """Tests for time-off list/create/update/delete views."""

    def setUp(self):
        self.user = User.objects.create_user(username="timeoffuser", password="12345")
        self.client_instance = TestClient()

        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_timeoff-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        UserPractice.objects.get_or_create(
            user=self.user, practice=self.practice, defaults={"is_owner": True}
        )
        self.client_instance.login(username="timeoffuser", password="12345")

        session = self.client_instance.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

        today = date.today()
        self.upcoming = TimeOff.objects.create(
            title="Sommerurlaub",
            type="vacation",
            start_date=today + timedelta(days=10),
            end_date=today + timedelta(days=20),
        )
        self.past = TimeOff.objects.create(
            title="Weihnachten",
            type="holiday",
            start_date=today - timedelta(days=20),
            end_date=today - timedelta(days=10),
        )

    def test_list_loads(self):
        response = self.client_instance.get(reverse("timeoff_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/time_off_list.html")

    def test_list_splits_upcoming_and_past(self):
        response = self.client_instance.get(reverse("timeoff_list"))
        self.assertIn(self.upcoming, response.context["upcoming"])
        self.assertIn(self.past, response.context["past"])
        self.assertNotIn(self.past, response.context["upcoming"])
        self.assertNotIn(self.upcoming, response.context["past"])

    def test_create_get(self):
        response = self.client_instance.get(reverse("timeoff_create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/time_off_form.html")

    def test_create_post_valid(self):
        today = date.today()
        response = self.client_instance.post(
            reverse("timeoff_create"),
            {
                "title": "Fortbildung",
                "type": "training",
                "start_date": (today + timedelta(days=5)).isoformat(),
                "end_date": (today + timedelta(days=6)).isoformat(),
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TimeOff.objects.filter(title="Fortbildung").exists())

    def test_create_post_invalid_end_before_start(self):
        today = date.today()
        response = self.client_instance.post(
            reverse("timeoff_create"),
            {
                "title": "Invalid",
                "type": "other",
                "start_date": (today + timedelta(days=5)).isoformat(),
                "end_date": (today + timedelta(days=1)).isoformat(),
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(TimeOff.objects.filter(title="Invalid").exists())

    def test_update_post(self):
        response = self.client_instance.post(
            reverse("timeoff_update", kwargs={"pk": self.upcoming.pk}),
            {
                "title": "Sommerurlaub (verlängert)",
                "type": "vacation",
                "start_date": self.upcoming.start_date.isoformat(),
                "end_date": self.upcoming.end_date.isoformat(),
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.upcoming.refresh_from_db()
        self.assertEqual(self.upcoming.title, "Sommerurlaub (verlängert)")

    def test_delete_get_shows_confirmation(self):
        response = self.client_instance.get(reverse("timeoff_delete", kwargs={"pk": self.past.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/time_off_confirm_delete.html")

    def test_delete_post_removes_entry(self):
        response = self.client_instance.post(reverse("timeoff_delete", kwargs={"pk": self.past.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TimeOff.objects.filter(pk=self.past.pk).exists())

    def test_update_404_for_nonexistent(self):
        response = self.client_instance.get(reverse("timeoff_update", kwargs={"pk": 99999}))
        self.assertEqual(response.status_code, 404)


class SendTimeOffNoticeViewTest(TestCase):
    """Tests for the heads-up email notice view."""

    def setUp(self):
        logging.getLogger("my_practice.email").setLevel(logging.ERROR)

        self.client_instance = TestClient()

        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_timeoff-notice-1",
            title="Test Practitioner",
            email="practice@test.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="noticeuser", password="12345")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance.login(username="noticeuser", password="12345")

        session = self.client_instance.session
        session["current_practice_slug"] = self.practice.slug
        session.save()

        today = date.today()
        self.time_off = TimeOff.objects.create(
            title="Sommerurlaub",
            type="vacation",
            start_date=today + timedelta(days=10),
            end_date=today + timedelta(days=20),
        )
        self.time_off_2 = TimeOff.objects.create(
            title="Weihnachten",
            type="holiday",
            start_date=today + timedelta(days=100),
            end_date=today + timedelta(days=105),
        )

        self.client_de = Client.objects.create(
            client_code="DE",
            full_name="Anna Schmidt",
            email="anna@example.com",
            language="de",
            active=True,
            practice=self.practice,
        )
        self.client_en = Client.objects.create(
            client_code="EN",
            full_name="Max Mustermann",
            email="max@example.com",
            language="en",
            active=True,
            practice=self.practice,
        )
        self.client_inactive = Client.objects.create(
            client_code="IN",
            full_name="Inactive Client",
            email="inactive@example.com",
            active=False,
            practice=self.practice,
        )
        self.client_no_email = Client.objects.create(
            client_code="NE",
            full_name="No Email Client",
            email="",
            active=True,
            practice=self.practice,
        )

        self.today = today
        self.last_session_date = today - timedelta(days=14)
        self.next_session_date = today + timedelta(days=7)
        Session.objects.create(
            client=self.client_de, session_date=self.last_session_date, cancelled=False
        )
        Session.objects.create(
            client=self.client_de, session_date=self.next_session_date, cancelled=False
        )

    def test_get_form_shows_recipient_table_with_code_language_and_sessions(self):
        response = self.client_instance.get(reverse("timeoff_notify"), {"ids": [self.time_off.pk]})
        self.assertEqual(response.status_code, 200)

        # All active/emailed recipients pre-checked by default.
        self.assertEqual(
            response.context["checked_ids"], {str(self.client_de.pk), str(self.client_en.pk)}
        )

        content = response.content.decode()
        # Privacy: client codes, not full names, appear in the recipient table.
        self.assertIn(self.client_de.client_code, content)
        self.assertIn(self.client_en.client_code, content)
        self.assertNotIn(self.client_de.full_name, content)
        self.assertNotIn(self.client_en.full_name, content)
        self.assertIn("DE</span>", content)
        self.assertIn("EN</span>", content)
        self.assertIn(self.last_session_date.isoformat(), content)
        self.assertIn(self.next_session_date.isoformat(), content)

    def test_get_form_loads_with_recipients_prechecked(self):
        response = self.client_instance.get(reverse("timeoff_notify"), {"ids": [self.time_off.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/time_off_notice_form.html")
        self.assertEqual(list(response.context["time_offs"]), [self.time_off])

        form = response.context["form"]
        recipient_pks = set(form.fields["recipients"].queryset.values_list("pk", flat=True))
        self.assertEqual(recipient_pks, {self.client_de.pk, self.client_en.pk})
        self.assertIn("{salutation}", form.initial["body_de"])
        self.assertIn("{salutation}", form.initial["body_en"])

    def test_get_form_loads_with_multiple_periods_selected(self):
        response = self.client_instance.get(
            reverse("timeoff_notify"), {"ids": [self.time_off.pk, self.time_off_2.pk]}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["time_offs"]), [self.time_off, self.time_off_2])
        form = response.context["form"]

        # Subject/body are date-based, not title-based — clients don't need to know
        # what the time off is for, just which dates/weekdays are affected.
        self.assertTrue(form.initial["subject_de"].startswith("Praxis geschlossen: "))
        periods = form.initial["subject_de"].removeprefix("Praxis geschlossen: ").split(", ")
        self.assertEqual(len(periods), 2)
        self.assertNotIn(self.time_off.title, form.initial["subject_de"])
        self.assertNotIn(self.time_off.title, form.initial["body_de"])

        body_lines = form.initial["body_de"].split("\n\n")[2].splitlines()
        self.assertEqual(len(body_lines), 2)
        self.assertTrue(all(line.startswith("- ") for line in body_lines))

    def test_get_404_when_no_ids_selected(self):
        response = self.client_instance.get(reverse("timeoff_notify"))
        self.assertEqual(response.status_code, 404)

    @patch("my_practice.views.timeoff_views.EmailMessage")
    def test_post_sends_to_selected_recipients_only(self, mock_email):
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance
        mock_instance.send.return_value = 1

        response = self.client_instance.post(
            reverse("timeoff_notify"),
            {
                "ids": [self.time_off.pk],
                "recipients": [self.client_de.pk],
                "subject_de": "Praxis geschlossen",
                "body_de": "{salutation},\n\nWir sind geschlossen.",
                "subject_en": "Practice closed",
                "body_en": "{salutation},\n\nWe are closed.",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(mock_email.call_count, 1)
        call_kwargs = mock_email.call_args.kwargs
        self.assertEqual(call_kwargs["to"], ["anna@example.com"])

    @patch("my_practice.views.timeoff_views.EmailMessage")
    def test_post_sends_language_specific_content_and_salutation(self, mock_email):
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance
        mock_instance.send.return_value = 1

        self.client_instance.post(
            reverse("timeoff_notify"),
            {
                "ids": [self.time_off.pk],
                "recipients": [self.client_de.pk, self.client_en.pk],
                "subject_de": "Praxis geschlossen",
                "body_de": "{salutation},\n\nWir sind geschlossen.",
                "subject_en": "Practice closed",
                "body_en": "{salutation},\n\nWe are closed.",
            },
        )
        self.assertEqual(mock_email.call_count, 2)
        calls_by_recipient = {c.kwargs["to"][0]: c.kwargs for c in mock_email.call_args_list}

        de_call = calls_by_recipient["anna@example.com"]
        self.assertEqual(de_call["subject"], "Praxis geschlossen")
        self.assertNotIn("{salutation}", de_call["body"])

        en_call = calls_by_recipient["max@example.com"]
        self.assertEqual(en_call["subject"], "Practice closed")
        self.assertNotIn("{salutation}", en_call["body"])

    def test_post_invalid_recipient_rejected(self):
        """A client outside the pre-scoped queryset (inactive/no email) can't be submitted."""
        response = self.client_instance.post(
            reverse("timeoff_notify"),
            {
                "ids": [self.time_off.pk],
                "recipients": [self.client_inactive.pk],
                "subject_de": "Praxis geschlossen",
                "body_de": "{salutation},\n\nWir sind geschlossen.",
                "subject_en": "Practice closed",
                "body_en": "{salutation},\n\nWe are closed.",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
