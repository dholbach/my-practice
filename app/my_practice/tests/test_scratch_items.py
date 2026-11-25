"""Reminders for next time (P-006 PR 2): ScratchItem, its views, the client page card and the log form."""

from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ..models import Client, ClientProfile, ScratchItem, Session, SessionLog
from ..utils.for_next_time import COVERED_SHOWN, build_for_next_time, clean_reminder
from .test_clinical import TEST_FERNET_KEY, ClinicalTestBase
from .test_helpers import create_test_practice


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class ScratchItemViewTests(ClinicalTestBase):
    def _url(self, name, *args):
        return reverse(name, args=[self.client_obj.pk, *args])

    def _item(self, text="ask about sleep", **fields):
        return ScratchItem.objects.create(client=self.client_obj, text=text, **fields)

    def test_create_adds_an_open_reminder_and_returns_to_the_profile_tab(self):
        response = self.http.post(self._url("scratch_item_create"), {"text": "  ask about sleep "})
        item = ScratchItem.objects.get()
        self.assertEqual(
            (item.text, item.done_at, item.client), ("ask about sleep", None, self.client_obj)
        )
        self.assertTrue(response.url.endswith("#ptab-profil"))

    def test_create_rejects_empty_text(self):
        self.http.post(self._url("scratch_item_create"), {"text": "   "})
        self.assertFalse(ScratchItem.objects.exists())

    def test_create_cuts_text_to_the_field_length(self):
        self.http.post(self._url("scratch_item_create"), {"text": "x" * 500})
        self.assertEqual(len(ScratchItem.objects.get().text), 300)

    def test_create_follows_a_safe_next_only(self):
        self.http.post(self._url("scratch_item_create"), {"text": "a"})
        response = self.http.post(
            self._url("scratch_item_create"), {"text": "b", "next": "https://evil.example/"}
        )
        self.assertTrue(response.url.startswith("/clients/"))

    def test_toggle_covers_and_reopens(self):
        item = self._item()
        self.http.post(self._url("scratch_item_toggle", item.pk))
        item.refresh_from_db()
        self.assertIsNotNone(item.done_at)
        self.http.post(self._url("scratch_item_toggle", item.pk))
        item.refresh_from_db()
        self.assertIsNone(item.done_at)

    def test_delete_removes_the_reminder(self):
        item = self._item()
        self.http.post(self._url("scratch_item_delete", item.pk))
        self.assertFalse(ScratchItem.objects.exists())

    def test_views_only_accept_post(self):
        item = self._item()
        for name, args in (
            ("scratch_item_create", ()),
            ("scratch_item_toggle", (item.pk,)),
            ("scratch_item_delete", (item.pk,)),
        ):
            self.assertEqual(self.http.get(self._url(name, *args)).status_code, 405, name)

    def test_another_practices_client_is_a_404_and_untouched(self):
        other_practice = create_test_practice(
            name="Other", slug="other-scratch", email="other@practice.example"
        )
        other_client = Client.objects.create(
            client_code="XX-9",
            full_name="Max Mustermann",
            email="max@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=other_practice,
        )
        foreign = ScratchItem.objects.create(client=other_client, text="not yours")
        for name, args in (
            ("scratch_item_create", ()),
            ("scratch_item_toggle", (foreign.pk,)),
            ("scratch_item_delete", (foreign.pk,)),
        ):
            url = reverse(name, args=[other_client.pk, *args])
            self.assertEqual(self.http.post(url, {"text": "x"}).status_code, 404, name)
        foreign.refresh_from_db()
        self.assertIsNone(foreign.done_at)
        self.assertEqual(ScratchItem.objects.filter(client=other_client).count(), 1)

    def test_an_item_of_another_client_cannot_be_reached_through_this_one(self):
        other = Client.objects.create(
            client_code="XX-8",
            full_name="Anna Schmidt",
            email="anna2@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        foreign = ScratchItem.objects.create(client=other, text="theirs")
        self.assertEqual(
            self.http.post(self._url("scratch_item_toggle", foreign.pk)).status_code, 404
        )

    def test_text_is_encrypted_at_rest_and_done_state_is_not(self):
        from django.db import connection

        self._item("sensitive wording")
        with connection.cursor() as cursor:
            cursor.execute("SELECT text FROM my_practice_scratchitem")
            raw = cursor.fetchone()[0]
        self.assertNotIn("sensitive", raw)

    def test_deleting_the_client_deletes_its_reminders(self):
        self._item()
        self.client_obj.delete()
        self.assertFalse(ScratchItem.objects.exists())


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class ForNextTimeTests(ClinicalTestBase):
    def test_collects_open_items_last_ideas_and_future_work(self):
        ScratchItem.objects.create(client=self.client_obj, text="open one")
        ScratchItem.objects.create(
            client=self.client_obj, text="covered one", done_at=timezone.now()
        )
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 13), duration=60
        )
        log = SessionLog.objects.create(session=session, next_session_ideas="Ressource Hund")
        ClientProfile.objects.create(
            client=self.client_obj,
            case_notes="## Zukünftige Arbeit / Fragen\nTitration klein halten",
        )
        result = build_for_next_time(self.client_obj)
        self.assertEqual([i.text for i in result["open_items"]], ["open one"])
        self.assertEqual([i.text for i in result["covered_items"]], ["covered one"])
        self.assertEqual(result["last_ideas_log"], log)
        self.assertEqual(result["future_work"], "Titration klein halten")

    def test_empty_client(self):
        result = build_for_next_time(self.client_obj)
        self.assertEqual(result["open_items"], [])
        self.assertIsNone(result["last_ideas_log"])
        self.assertEqual(result["future_work"], "")

    def test_only_the_latest_covered_items_are_listed(self):
        for n in range(COVERED_SHOWN + 3):
            ScratchItem.objects.create(client=self.client_obj, text=f"c{n}", done_at=timezone.now())
        self.assertEqual(len(build_for_next_time(self.client_obj)["covered_items"]), COVERED_SHOWN)


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class ForNextTimeCardAndLogFormTests(ClinicalTestBase):
    def _detail(self):
        return self.http.get(reverse("client_detail", kwargs={"pk": self.client_obj.pk}))

    def test_client_page_shows_the_card_with_open_reminders_and_the_add_form(self):
        ScratchItem.objects.create(client=self.client_obj, text="ask about sleep")
        response = self._detail()
        self.assertContains(response, 'id="for-next-time"')
        self.assertContains(response, "ask about sleep")
        self.assertContains(
            response, reverse("scratch_item_create", kwargs={"pk": self.client_obj.pk})
        )

    def test_covered_reminders_are_listed_apart_from_the_open_ones(self):
        ScratchItem.objects.create(
            client=self.client_obj, text="done thing", done_at=timezone.now()
        )
        response = self._detail()
        self.assertContains(response, "cn-next-covered")
        self.assertContains(response, "done thing")

    def _log_form(self):
        return self.http.get(reverse("session_log_create", kwargs={"pk": self.client_obj.pk}))

    def test_log_form_lists_open_reminders_as_checkboxes_tied_to_the_form(self):
        item = ScratchItem.objects.create(client=self.client_obj, text="ask about sleep")
        response = self._log_form()
        self.assertContains(response, 'name="scratch_done"')
        self.assertContains(response, f'value="{item.pk}" form="session-log-form"')

    def test_log_form_leaves_covered_reminders_out(self):
        ScratchItem.objects.create(
            client=self.client_obj, text="done thing", done_at=timezone.now()
        )
        self.assertNotContains(self._log_form(), "done thing")

    def _post_log(self, url, **extra):
        return self.http.post(url, {"session_date": "2026-03-20", "content": "x", **extra})

    def test_saving_a_new_log_covers_the_ticked_reminders_only(self):
        ticked = ScratchItem.objects.create(client=self.client_obj, text="a")
        untouched = ScratchItem.objects.create(client=self.client_obj, text="b")
        self._post_log(
            reverse("session_log_create", kwargs={"pk": self.client_obj.pk}),
            scratch_done=[str(ticked.pk), "not-a-number"],
        )
        ticked.refresh_from_db()
        untouched.refresh_from_db()
        self.assertIsNotNone(ticked.done_at)
        self.assertIsNone(untouched.done_at)

    def test_saving_an_edited_log_covers_ticked_reminders_too(self):
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), duration=60
        )
        log = SessionLog.objects.create(session=session, content="x")
        item = ScratchItem.objects.create(client=self.client_obj, text="a")
        url = reverse(
            "session_log_edit", kwargs={"client_pk": self.client_obj.pk, "log_pk": log.pk}
        )
        self.http.post(url, {"content": "x", "scratch_done": [str(item.pk)]})
        item.refresh_from_db()
        self.assertIsNotNone(item.done_at)

    def test_a_ticked_reminder_of_another_client_is_ignored(self):
        other = Client.objects.create(
            client_code="XX-8",
            full_name="Anna Schmidt",
            email="anna2@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        foreign = ScratchItem.objects.create(client=other, text="theirs")
        self._post_log(
            reverse("session_log_create", kwargs={"pk": self.client_obj.pk}),
            scratch_done=[str(foreign.pk)],
        )
        foreign.refresh_from_db()
        self.assertIsNone(foreign.done_at)


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class AddRemindersFromLogFormTests(ClinicalTestBase):
    """Reminders typed into the log form's side panel are created when the log is saved."""

    def _create_url(self):
        return reverse("session_log_create", kwargs={"pk": self.client_obj.pk})

    def _post(self, scratch_new):
        return self.http.post(
            self._create_url(),
            {"session_date": "2026-03-20", "content": "x", "scratch_new": scratch_new},
        )

    def _texts(self):
        return [item.text for item in ScratchItem.objects.filter(client=self.client_obj)]

    def test_one_reminder_per_non_empty_line(self):
        self._post("ask about sleep\n\n  Hund mitbringen  \n   \n")
        self.assertEqual(self._texts(), ["ask about sleep", "Hund mitbringen"])

    def test_the_new_reminders_are_open(self):
        self._post("a")
        self.assertIsNone(ScratchItem.objects.get().done_at)

    def test_nothing_is_created_for_an_empty_field(self):
        self._post("")
        self._post(" \n ")
        self.assertEqual(self._texts(), [])

    def test_long_lines_are_cut_and_the_number_is_capped(self):
        from ..views.clinical_views import MAX_NEW_SCRATCH_ITEMS

        self._post("\n".join(["x" * 400] + [f"line {n}" for n in range(30)]))
        texts = self._texts()
        self.assertEqual(len(texts), MAX_NEW_SCRATCH_ITEMS)
        self.assertEqual(len(texts[0]), 300)

    def test_editing_a_log_can_add_reminders_too(self):
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), duration=60
        )
        log = SessionLog.objects.create(session=session, content="x")
        url = reverse(
            "session_log_edit", kwargs={"client_pk": self.client_obj.pk, "log_pk": log.pk}
        )
        self.http.post(url, {"content": "x", "scratch_new": "from the edit page"})
        self.assertEqual(self._texts(), ["from the edit page"])

    def test_a_ticked_reminder_and_a_new_one_in_the_same_save(self):
        old = ScratchItem.objects.create(client=self.client_obj, text="old")
        self.http.post(
            self._create_url(),
            {
                "session_date": "2026-03-20",
                "content": "x",
                "scratch_done": [str(old.pk)],
                "scratch_new": "new",
            },
        )
        old.refresh_from_db()
        self.assertIsNotNone(old.done_at)
        self.assertEqual(self._texts(), ["old", "new"])

    def test_the_panel_offers_the_field_on_the_edit_page_as_well(self):
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), duration=60
        )
        log = SessionLog.objects.create(session=session, content="x")
        url = reverse(
            "session_log_edit", kwargs={"client_pk": self.client_obj.pk, "log_pk": log.pk}
        )
        self.assertContains(self.http.get(url), 'name="scratch_new" form="session-log-form"')


class CleanReminderTests(SimpleTestCase):
    def test_removes_a_leading_list_marker(self):
        for raw in ("- ask", " - ask", "-   ask", "* ask", "• ask", "\t- ask  "):
            self.assertEqual(clean_reminder(raw), "ask", repr(raw))

    def test_keeps_text_that_only_starts_like_a_marker(self):
        for raw in ("-5 Grad draußen", "*wichtig* nachfragen", "--", "Hund - Bruder"):
            self.assertEqual(clean_reminder(raw), raw)

    def test_a_marker_alone_leaves_nothing(self):
        for raw in ("- ", "-", " * ", "   "):
            self.assertEqual(clean_reminder(raw), "", repr(raw))

    def test_only_the_first_marker_goes(self):
        self.assertEqual(clean_reminder("- - ask"), "- ask")

    def test_cut_to_the_field_length_after_the_marker_is_removed(self):
        self.assertEqual(len(clean_reminder("- " + "x" * 400)), 300)


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class ListMarkersInTheFormTests(ClinicalTestBase):
    def test_pasted_list_loses_its_markers_in_the_log_form(self):
        self.http.post(
            reverse("session_log_create", kwargs={"pk": self.client_obj.pk}),
            {
                "session_date": "2026-03-20",
                "content": "x",
                "scratch_new": "- ask about sleep\n - bring the dog",
            },
        )
        self.assertEqual(
            [i.text for i in ScratchItem.objects.all()], ["ask about sleep", "bring the dog"]
        )

    def test_the_client_page_form_strips_the_marker_too(self):
        self.http.post(
            reverse("scratch_item_create", kwargs={"pk": self.client_obj.pk}), {"text": "- ask"}
        )
        self.assertEqual(ScratchItem.objects.get().text, "ask")
