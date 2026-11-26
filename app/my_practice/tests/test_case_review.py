"""The case review (P-006 PR 6): what happened since the last one, the page, and finishing."""

from datetime import date, timedelta
from decimal import Decimal

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from ..models import CaseReview, Client, ClinicalFact, Session, SessionLog, SupervisionItem
from ..utils.case_review import (
    INVITE_AFTER_SESSIONS,
    build_review,
    finish_review,
    last_review,
    review_invitation,
    sessions_since,
)
from ..utils.case_sheet import add_line, change_line
from .test_clinical import TEST_FERNET_KEY, ClinicalTestBase
from .test_helpers import create_test_practice


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class ReviewBase(ClinicalTestBase):
    def _session(self, day, *, log=True, cancelled=False, **log_fields):
        session = Session.objects.create(
            client=self.client_obj,
            session_date=date(2026, 3, 1) + timedelta(days=day),
            duration=60,
            cancelled=cancelled,
        )
        if log:
            SessionLog.objects.create(session=session, **log_fields)
        return session

    def _review(self, day):
        return CaseReview.objects.create(
            client=self.client_obj, reviewed_on=date(2026, 3, 1) + timedelta(days=day)
        )

    def _other_client(self):
        return Client.objects.create(
            client_code="XX-9",
            full_name="Max Mustermann",
            email="max@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )


class SessionsSinceTests(ReviewBase):
    def test_everything_when_never_reviewed_oldest_first(self):
        late = self._session(9)
        early = self._session(2)
        self.assertEqual(list(sessions_since(self.client_obj, None)), [early, late])

    def test_only_sessions_after_the_last_review_day(self):
        self._session(2)
        on_the_day = self._session(5)
        after = self._session(6)
        review = self._review(5)
        self.assertEqual(list(sessions_since(self.client_obj, review)), [after])
        self.assertNotIn(on_the_day, sessions_since(self.client_obj, review))

    def test_cancelled_and_future_sessions_do_not_count_but_today_does(self):
        held = self._session(1)
        self._session(2, cancelled=True)
        today = Session.objects.create(
            client=self.client_obj, session_date=timezone.localdate(), duration=60
        )
        Session.objects.create(
            client=self.client_obj,
            session_date=timezone.localdate() + timedelta(days=3),
            duration=60,
        )
        self.assertEqual(list(sessions_since(self.client_obj, None)), [held, today])

    def test_last_review_is_the_newest(self):
        self.assertIsNone(last_review(self.client_obj))
        self._review(3)
        newest = self._review(8)
        self.assertEqual(last_review(self.client_obj), newest)

    def test_other_clients_sessions_never_count(self):
        Session.objects.create(
            client=self._other_client(), session_date=date(2026, 3, 2), duration=60
        )
        self.assertEqual(list(sessions_since(self.client_obj, None)), [])


class InvitationTests(ReviewBase):
    def test_none_until_enough_sessions_have_piled_up(self):
        for day in range(INVITE_AFTER_SESSIONS - 1):
            self._session(day)
        self.assertIsNone(review_invitation(self.client_obj))
        self._session(10)
        self.assertEqual(
            review_invitation(self.client_obj), {"count": INVITE_AFTER_SESSIONS, "since": None}
        )

    def test_counts_from_the_last_review(self):
        for day in range(5):
            self._session(day)
        self._review(2)  # sessions on days 3 and 4 are after it
        self.assertIsNone(review_invitation(self.client_obj))
        self._session(8)
        self.assertEqual(
            review_invitation(self.client_obj), {"count": 3, "since": date(2026, 3, 3)}
        )

    def test_a_review_resets_the_invitation(self):
        for day in range(5):
            self._session(day)
        finish_review(self.client_obj, today=date(2026, 3, 30))
        self.assertIsNone(review_invitation(self.client_obj))


class BuildReviewTests(ReviewBase):
    def test_a_sessions_text_is_broken_into_lines_and_reflection_stays_apart(self):
        self._session(
            1,
            summary="Ressourcenarbeit",
            mood_tags=["gute_ressourcen"],
            content="Gefühl danach: ruhig\n\n  Sitzung: Hund \n",
            next_session_ideas="Wald\nBruder",
            therapist_reflection="Schwer auszuhalten",
        )
        (block,) = build_review(self.client_obj)["blocks"]
        self.assertEqual(block.summary, "Ressourcenarbeit")
        self.assertEqual(block.mood_tags, ["gute_ressourcen"])
        self.assertEqual(block.note_lines, ["Gefühl danach: ruhig", "Sitzung: Hund"])
        self.assertEqual(block.idea_lines, ["Wald", "Bruder"])
        self.assertEqual(block.reflection, "Schwer auszuhalten")
        self.assertNotIn("Schwer auszuhalten", block.note_lines + block.idea_lines)
        self.assertTrue(block.has_log)

    def test_a_session_without_a_log_is_listed_as_such(self):
        self._session(1, log=False)
        (block,) = build_review(self.client_obj)["blocks"]
        self.assertFalse(block.has_log)
        self.assertEqual((block.note_lines, block.idea_lines), ([], []))

    def test_hypothesis_cell_with_its_earlier_versions(self):
        first = add_line(self.client_obj, "hypothesis", "", "v1", today=date(2026, 1, 1))
        change_line(first, "v2", today=date(2026, 2, 1))
        cell = build_review(self.client_obj)["hypothesis"]
        self.assertEqual([f.content for f in cell.lines], ["v2"])
        self.assertEqual([f.content for f in cell.history], ["v1"])

    def test_then_and_now_needs_two_of_the_clients_own_words(self):
        add_line(self.client_obj, "in_their_words", "", "unter Strom", today=date(2026, 1, 1))
        self.assertIsNone(build_review(self.client_obj)["then_and_now"])
        add_line(self.client_obj, "in_their_words", "", "Strom leiser", today=date(2026, 3, 1))
        add_line(self.client_obj, "in_their_words", "", "dazwischen", today=date(2026, 2, 1))
        then, now = build_review(self.client_obj)["then_and_now"]
        self.assertEqual((then.content, now.content), ("unter Strom", "Strom leiser"))

    def test_still_empty_lists_rows_without_current_lines_but_not_the_catch_all(self):
        add_line(self.client_obj, "resources", "", "Hund")
        add_line(self.client_obj, "symptoms", "onset", "Frühjahr")
        empty = build_review(self.client_obj)["still_empty"]
        self.assertNotIn("Ressourcen", empty)
        self.assertNotIn("Symptomatik", empty)  # one filled cell is enough
        self.assertIn("Anliegen", empty)
        self.assertNotIn("Weitere Notizen", empty)

    def test_a_resolved_line_no_longer_counts_as_filled(self):
        line = add_line(self.client_obj, "resources", "", "Hund")
        ClinicalFact.objects.filter(pk=line.pk).update(status="resolved")
        self.assertIn("Ressourcen", build_review(self.client_obj)["still_empty"])

    def test_added_today_lists_lines_noted_today_with_their_row_and_cell(self):
        add_line(self.client_obj, "symptoms", "onset", "Frühjahr")
        add_line(self.client_obj, "resources", "", "alt", today=date(2026, 1, 1))
        added = build_review(self.client_obj)["added_today"]
        self.assertEqual(added, [{"row": "Symptomatik", "cell": "Beginn", "content": "Frühjahr"}])

    def test_only_open_supervision_topics(self):
        SupervisionItem.objects.create(client=self.client_obj, content="offen")
        SupervisionItem.objects.create(
            client=self.client_obj, content="erledigt", status="besprochen"
        )
        self.assertEqual(
            [i.content for i in build_review(self.client_obj)["open_supervision"]], ["offen"]
        )

    def test_other_clients_data_never_appears(self):
        other = self._other_client()
        add_line(other, "resources", "", "theirs")
        add_line(other, "in_their_words", "", "a")
        add_line(other, "in_their_words", "", "b")
        SupervisionItem.objects.create(client=other, content="theirs")
        review = build_review(self.client_obj)
        self.assertIsNone(review["then_and_now"])
        self.assertEqual(review["open_supervision"], [])
        self.assertEqual(review["added_today"], [])
        self.assertIn("Ressourcen", review["still_empty"])


class FinishReviewTests(ReviewBase):
    def test_finishing_records_today(self):
        review = finish_review(self.client_obj)
        self.assertEqual(
            (review.client, review.reviewed_on), (self.client_obj, timezone.localdate())
        )

    def test_finishing_twice_on_a_day_keeps_one_record(self):
        finish_review(self.client_obj)
        finish_review(self.client_obj)
        self.assertEqual(CaseReview.objects.count(), 1)


class ReviewViewTests(ReviewBase):
    def _url(self):
        return reverse("case_review", kwargs={"pk": self.client_obj.pk})

    def _finish_url(self):
        return reverse("case_review_finish", kwargs={"pk": self.client_obj.pk})

    def test_the_page_lists_sessions_since_the_last_review(self):
        self._session(1, summary="alte Sitzung")
        self._review(3)
        self._session(6, summary="neue Sitzung", content="Sitzung: Hund")
        html = self.http.get(self._url()).content.decode()
        self.assertIn("neue Sitzung", html)
        self.assertNotIn("alte Sitzung", html)

    def test_each_line_has_a_prefilled_form_carrying_its_session_and_the_way_back(self):
        session = self._session(1, content="Sitzung: Hund")
        html = self.http.get(self._url()).content.decode()
        form = html.split('class="rv-line"')[1].split("</form>")[0]
        self.assertIn(reverse("case_fact_add", kwargs={"pk": self.client_obj.pk}), form)
        self.assertIn(f'name="source_session" value="{session.pk}"', form)
        self.assertIn(f'name="next" value="{self._url()}"', form)
        self.assertRegex(form, r"<textarea[^>]*>Sitzung: Hund</textarea>")
        self.assertIn('value="resources|"', form)

    def test_the_own_reflection_is_shown_to_read_but_cannot_be_sent(self):
        self._session(1, therapist_reflection="Schwer auszuhalten")
        html = self.http.get(self._url()).content.decode()
        self.assertIn("Schwer auszuhalten", html)
        self.assertNotIn('class="rv-line"', html)  # no line, hence no send form

    def test_sending_a_line_returns_to_the_review_and_credits_the_session(self):
        session = self._session(1, content="Sitzung: Hund")
        response = self.http.post(
            reverse("case_fact_add", kwargs={"pk": self.client_obj.pk}),
            {
                "target": "resources|",
                "content": "Hund",
                "source_session": session.pk,
                "next": self._url(),
            },
        )
        self.assertEqual(response.url, self._url())
        self.assertEqual(ClinicalFact.objects.get().source_session, session)
        self.assertIn(
            "Hund", self.http.get(self._url()).content.decode()
        )  # now under "added today"

    def test_an_empty_review_says_so(self):
        self.assertEqual(self.http.get(self._url()).context["blocks"], [])

    def test_the_page_changes_nothing(self):
        self._session(1)
        self.http.get(self._url())
        self.assertFalse(CaseReview.objects.exists())
        self.assertFalse(ClinicalFact.objects.exists())

    def test_finishing_records_the_review_and_goes_back_to_the_sheet(self):
        response = self.http.post(self._finish_url())
        self.assertEqual(CaseReview.objects.get().reviewed_on, timezone.localdate())
        self.assertTrue(response.url.endswith("#case-sheet"))

    def test_after_finishing_the_page_starts_empty(self):
        self._session(1)
        self.http.post(self._finish_url())
        # the session was before today: it is now behind the review
        self.assertEqual(self.http.get(self._url()).context["blocks"], [])

    def test_the_methods_are_enforced(self):
        self.assertEqual(self.http.post(self._url()).status_code, 405)
        self.assertEqual(self.http.get(self._finish_url()).status_code, 405)

    def test_another_practices_client_is_a_404(self):
        other_practice = create_test_practice(
            name="Other", slug="other-review", email="o@practice.example"
        )
        foreign = Client.objects.create(
            client_code="XX-7",
            full_name="Max Mustermann",
            email="max7@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=other_practice,
        )
        self.assertEqual(
            self.http.get(reverse("case_review", kwargs={"pk": foreign.pk})).status_code, 404
        )
        self.assertEqual(
            self.http.post(reverse("case_review_finish", kwargs={"pk": foreign.pk})).status_code,
            404,
        )
        self.assertFalse(CaseReview.objects.exists())

    def test_deleting_the_client_deletes_its_reviews(self):
        self._review(1)
        self.client_obj.delete()
        self.assertFalse(CaseReview.objects.exists())


class ClientPageReviewTests(ReviewBase):
    def _html(self):
        return self.http.get(
            reverse("client_detail", kwargs={"pk": self.client_obj.pk})
        ).content.decode()

    def test_no_invitation_with_few_sessions(self):
        self._session(1)
        self.assertNotIn(reverse("case_review", kwargs={"pk": self.client_obj.pk}), self._html())

    def test_the_invitation_appears_once_sessions_have_piled_up_and_links_to_the_review(self):
        for day in range(INVITE_AFTER_SESSIONS):
            self._session(day)
        self.assertIn(reverse("case_review", kwargs={"pk": self.client_obj.pk}), self._html())

    def test_a_review_shows_as_a_marker_in_the_timeline(self):
        self._session(1, summary="x", content="y")
        self._review(5)
        timeline = self._html().split('id="cn-timeline"')[1]
        self.assertIn("cn-review-marker", timeline)
        self.assertIn("06.03.2026", timeline.split("cn-review-marker")[1][:200])

    def test_no_marker_without_a_review(self):
        self._session(1, summary="x", content="y")
        self.assertNotIn("cn-review-marker", self._html())
