"""The session log form (P-006 PR 1): prompt chips, the "More" fields and the context panel."""

import re
from datetime import date
from decimal import Decimal

from django.test import override_settings
from django.urls import reverse

from ..models import Client, ClinicalFact, Session, SessionLog
from ..utils.case_sheet import add_line
from ..utils.session_log_helpers import build_log_context
from .test_clinical import TEST_FERNET_KEY, ClinicalTestBase


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class BuildLogContextTests(ClinicalTestBase):
    def _log(self, day, *, client=None, **fields):
        session = Session.objects.create(
            client=client or self.client_obj, session_date=date(2026, 3, day), duration=60
        )
        return SessionLog.objects.create(session=session, **fields)

    def _context(self, **kwargs):
        kwargs.setdefault("before", None)
        kwargs.setdefault("exclude_log_pk", None)
        return build_log_context(self.client_obj, **kwargs)

    def test_previous_log_is_the_most_recent_one_with_ideas(self):
        self._log(1, next_session_ideas="old idea")
        latest = self._log(8, next_session_ideas="Ressource ausbauen")
        self.assertEqual(self._context()["previous_log"], latest)

    def test_no_previous_log_when_the_latest_has_no_ideas(self):
        """Ideas from two sessions back are not shown as if they were last session's."""
        self._log(1, next_session_ideas="old idea")
        self._log(8, summary="no ideas this time")
        self.assertIsNone(self._context()["previous_log"])

    def test_recent_logs_are_three_newest_with_a_summary(self):
        for day in (1, 2, 3, 4):
            self._log(day, summary=f"day {day}")
        self._log(5)  # newest, but no one-liner
        summaries = [log.summary for log in self._context()["recent_logs"]]
        self.assertEqual(summaries, ["day 4", "day 3"])

    def test_before_leaves_out_later_sessions(self):
        self._log(1, summary="early")
        self._log(20, summary="late")
        context = self._context(before=date(2026, 3, 10))
        self.assertEqual([log.summary for log in context["recent_logs"]], ["early"])

    def test_before_excludes_a_session_on_the_same_day(self):
        self._log(10, summary="same day")
        self.assertEqual(self._context(before=date(2026, 3, 10))["recent_logs"], [])

    def test_the_log_being_edited_is_left_out(self):
        self._log(1, summary="earlier")
        own = self._log(8, summary="own", next_session_ideas="own idea")
        context = self._context(exclude_log_pk=own.pk)
        self.assertEqual([log.summary for log in context["recent_logs"]], ["earlier"])
        self.assertIsNone(context["previous_log"])

    def test_other_clients_logs_never_appear(self):
        other = Client.objects.create(
            client_code="XX-9",
            full_name="Max Mustermann",
            email="max@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        self._log(1, client=other, summary="not yours", next_session_ideas="not yours")
        context = self._context()
        self.assertEqual(context["recent_logs"], [])
        self.assertIsNone(context["previous_log"])

    def test_case_sheet_excerpt_lists_rows_with_current_lines_in_sheet_order(self):
        add_line(self.client_obj, "future_work", "", "Titration klein halten")
        add_line(self.client_obj, "hypothesis", "", "Übererregung")
        add_line(self.client_obj, "resources", "", "Hund")
        add_line(self.client_obj, "resources", "", "Wald")
        add_line(self.client_obj, "beliefs", "", "not in the excerpt")
        self.assertEqual(
            self._context()["case_sheet_excerpt"],
            [
                ("Arbeitshypothese", "Übererregung"),
                ("Ressourcen", "- Hund\n- Wald"),
                ("Zukünftige Arbeit / Fragen", "Titration klein halten"),
            ],
        )

    def test_the_excerpt_leaves_out_replaced_and_resolved_lines(self):
        first = add_line(self.client_obj, "hypothesis", "", "alt")
        add_line(self.client_obj, "hypothesis", "", "neu")
        trigger = add_line(self.client_obj, "current_triggers", "", "weg")
        ClinicalFact.objects.filter(pk=trigger.pk).update(status="resolved")
        self.assertEqual(self._context()["case_sheet_excerpt"], [("Arbeitshypothese", "neu")])
        self.assertEqual(ClinicalFact.objects.get(pk=first.pk).status, "superseded")

    def test_an_empty_sheet_has_no_excerpt(self):
        self.assertEqual(self._context()["case_sheet_excerpt"], [])


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class SessionLogFormViewTests(ClinicalTestBase):
    def _create_url(self):
        return reverse("session_log_create", kwargs={"pk": self.client_obj.pk})

    def test_create_form_offers_prompt_chips_and_prefills_nothing(self):
        response = self.http.get(self._create_url())
        self.assertContains(response, 'data-prompt-text="Gefühl danach: "')
        self.assertContains(response, 'data-prompt-text="Was half: "')
        self.assertNotContains(response, "## Gefühl danach")
        body = re.search(
            r'<textarea id="id_content"[^>]*>(.*?)</textarea>', response.content.decode(), re.S
        )
        self.assertEqual(body.group(1), "")

    def test_reflection_chip_writes_its_prompt_into_the_reflection_field(self):
        response = self.http.get(self._create_url())
        html = response.content.decode()
        chip = html.split('data-prompt-target="id_therapist_reflection"')[1].split(">")[0]
        self.assertIn('data-prompt-text="Wie ging es mir dabei: "', chip)
        self.assertContains(response, 'id="id_therapist_reflection"')

    def test_a_field_holding_only_a_prompt_is_saved_as_empty(self):
        self.http.post(
            self._create_url(),
            {
                "session_date": "2026-03-20",
                "content": "Sitzung: ",
                "therapist_reflection": "Wie ging es mir dabei: ",
                "interventions": "Pendeln",
            },
        )
        log = SessionLog.objects.get(session__client=self.client_obj)
        self.assertEqual((log.content, log.therapist_reflection), ("", ""))
        self.assertEqual(log.interventions, "Pendeln")

    def test_a_prompt_followed_by_text_is_kept(self):
        self.http.post(
            self._create_url(),
            {"session_date": "2026-03-20", "content": "Sitzung: ruhig"},
        )
        self.assertEqual(SessionLog.objects.get().content, "Sitzung: ruhig")

    def test_more_fields_are_collapsed_on_a_new_log(self):
        response = self.http.get(self._create_url())
        self.assertRegex(response.content.decode(), r'<details class="cn-more"\s*>')

    def test_more_fields_open_when_the_log_has_interventions_or_ideas(self):
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), duration=60
        )
        log = SessionLog.objects.create(session=session, interventions="Pendeln")
        url = reverse(
            "session_log_edit", kwargs={"client_pk": self.client_obj.pk, "log_pk": log.pk}
        )
        self.assertRegex(
            self.http.get(url).content.decode(), r'<details class="cn-more"\s+open\s*>'
        )

    def test_context_panel_shows_last_ideas_recent_one_liners_and_case_notes(self):
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 13), duration=60
        )
        SessionLog.objects.create(
            session=session, summary="Telefon als Trigger", next_session_ideas="Ressource Hund"
        )
        add_line(self.client_obj, "hypothesis", "", "Übererregung")
        response = self.http.get(self._create_url())
        self.assertContains(response, "cn-log-context")  # headings are translated, so match markup
        self.assertContains(response, "Ressource Hund")
        self.assertContains(response, "Telefon als Trigger")
        self.assertContains(response, "Übererregung")

    def test_a_client_without_history_gets_no_context_but_can_still_add_reminders(self):
        response = self.http.get(self._create_url())
        self.assertEqual(response.context["recent_logs"], [])
        self.assertIsNone(response.context["previous_log"])
        self.assertEqual(response.context["case_sheet_excerpt"], [])
        self.assertContains(response, 'name="scratch_new" form="session-log-form"')

    def test_session_date_limits_the_context_to_earlier_sessions(self):
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), duration=60
        )
        SessionLog.objects.create(session=session, summary="later session")
        response = self.http.get(self._create_url() + "?session_date=2026-03-10")
        self.assertNotContains(response, "later session")

    def test_edit_form_leaves_the_log_itself_out_of_the_context(self):
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), duration=60
        )
        log = SessionLog.objects.create(session=session, summary="only mine")
        url = reverse(
            "session_log_edit", kwargs={"client_pk": self.client_obj.pk, "log_pk": log.pk}
        )
        self.assertEqual(self.http.get(url).context["recent_logs"], [])
