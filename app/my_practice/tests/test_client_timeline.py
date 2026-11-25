"""The protocol timeline on the client page (P-006 PR 3b): layout, folded notes and search hooks."""

import re
from datetime import date, timedelta

from django.test import override_settings
from django.urls import reverse

from ..models import ClientNote, Session, SessionLog, SupervisionItem
from .test_clinical import TEST_FERNET_KEY, ClinicalTestBase


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class ClientTimelineTests(ClinicalTestBase):
    def _session(self, days_ago, **log_fields):
        """A session with a log, `days_ago` days before 2026-03-30."""
        session = Session.objects.create(
            client=self.client_obj,
            session_date=date(2026, 3, 30) - timedelta(days=days_ago),
            duration=60,
        )
        SessionLog.objects.create(session=session, **log_fields)
        return session

    def _response(self):
        return self.http.get(reverse("client_detail", kwargs={"pk": self.client_obj.pk}))

    def _timeline(self, response=None):
        html = (response or self._response()).content.decode()
        start = html.index('id="cn-timeline"')
        return html[start : html.index("<!-- Clinical questionnaires", start)]

    def _entries(self, timeline):
        """The timeline's entries as separate HTML chunks (split on the entry root classes)."""
        return re.split(
            r'(?=<div class="cn-(?:session-row|note-item|supervision-item) cn-timeline-entry)',
            timeline,
        )[1:]

    # ── layout ──

    def test_interventions_sit_in_the_left_column_and_tags_beside_the_one_liner(self):
        self._session(
            0,
            summary="Ressourcenarbeit",
            interventions="Pendeln",
            content="Sitzung: ruhig",
            mood_tags=["gute_ressourcen"],
        )
        row = self._entries(self._timeline())[0]
        left, right = row.split('<div class="cn-session-content">')
        self.assertIn("Pendeln", left)
        self.assertNotIn("Pendeln", right)  # not repeated on the right
        headline = right.split('<div class="cn-session-headline">')[1].split("</div>")[0]
        self.assertIn("Ressourcenarbeit", headline)
        self.assertIn("cn-tag-gute_ressourcen", headline)
        self.assertNotIn("cn-tag-gute_ressourcen", left)

    def test_the_note_is_folded_behind_a_summary_labelled_session_note(self):
        self._session(0, summary="x", content="Langer Text")
        self._session(10, summary="y", content="Alter Text")
        first, second = self._entries(self._timeline())[:2]
        self.assertIn('<details class="cn-note-fold" open>', first)
        self.assertIn('<details class="cn-note-fold">', second)

    def test_only_the_newest_session_with_a_note_is_open(self):
        newest_without_note = self._session(0, summary="just a one-liner")
        with_note = self._session(5, summary="x", content="Text")
        self._session(9, summary="y", content="Text")
        response = self._response()
        self.assertEqual(response.context["open_note_session_id"], with_note.pk)
        self.assertNotEqual(response.context["open_note_session_id"], newest_without_note.pk)
        self.assertEqual(self._timeline(response).count('cn-note-fold" open'), 1)

    def test_a_log_with_only_a_one_liner_has_no_fold(self):
        self._session(0, summary="just a one-liner")
        row = self._entries(self._timeline())[0]
        self.assertIn("just a one-liner", row)
        self.assertNotIn("cn-note-fold", row)

    def test_reflection_and_ideas_stay_inside_the_fold_as_their_own_details(self):
        self._session(
            0, summary="x", therapist_reflection="Schwer auszuhalten", next_session_ideas="Hund"
        )
        row = self._entries(self._timeline())[0]
        fold = row.split('<details class="cn-note-fold"')[1]
        self.assertIn("Schwer auszuhalten", fold)
        self.assertIn("Hund", fold)
        self.assertEqual(fold.count('<details class="cn-reflection">'), 2)

    def test_no_context_for_open_note_without_any_notes(self):
        self._session(0, summary="only")
        self.assertIsNone(self._response().context["open_note_session_id"])

    # ── older entries ──

    def test_entries_beyond_the_tenth_are_marked_old_and_get_a_plain_toggle(self):
        for days in range(12):
            self._session(days, summary=f"s{days}", content="x")
        timeline = self._timeline()
        entries = self._entries(timeline)
        self.assertEqual(len(entries), 12)
        self.assertEqual(sum("cn-timeline-old" in e for e in entries), 2)
        self.assertNotIn("cn-timeline-old", "".join(entries[:10]))
        self.assertIn('data-timeline-toggle="#cn-timeline"', timeline)
        self.assertIn("data-label-show=", timeline)
        self.assertNotIn("showOld", timeline)  # no Alpine state any more

    def test_ten_entries_or_fewer_get_no_toggle(self):
        for days in range(10):
            self._session(days, summary=f"s{days}", content="x")
        self.assertNotIn("data-timeline-toggle", self._timeline())

    # ── search hooks ──

    def test_the_search_input_is_wired_to_the_list_count_and_empty_message(self):
        self._session(0, summary="x", content="y")
        html = self._response().content.decode()
        self.assertRegex(html, r'<input type="search"[^>]*data-timeline-search="#cn-timeline"')
        for needle in (
            'data-timeline-count="#cn-timeline-count"',
            'data-timeline-empty="#cn-timeline-empty"',
            'data-count-template="{count} ',
        ):
            self.assertIn(needle, html)
        self.assertIn('id="cn-timeline-count"', html)
        self.assertRegex(html, r'<p id="cn-timeline-empty"[^>]*\shidden>')
        self.assertIn("js/timeline_search.js", html)

    def test_searchable_text_is_marked_for_every_kind_of_entry(self):
        self._session(0, summary="Ein Einzeiler", content="Ein Notiztext", interventions="Pendeln")
        ClientNote.objects.create(
            client=self.client_obj, note_date=date(2026, 3, 29), content="Telefonat mit Bruder"
        )
        SupervisionItem.objects.create(client=self.client_obj, content="Tempo halten?")
        timeline = self._timeline()
        for text in (
            "Ein Einzeiler",
            "Ein Notiztext",
            "Pendeln",
            "Telefonat mit Bruder",
            "Tempo halten?",
        ):
            self.assertRegex(timeline, r"cn-searchable[^>]*>[^<]*(<p>)?" + re.escape(text), text)

    def test_button_labels_are_not_searchable(self):
        self._session(0, summary="x", content="y")
        timeline = self._timeline()
        for part in re.findall(r"<(?:a|button)[^>]*cn-searchable", timeline):
            self.fail(f"a control is marked searchable: {part}")

    def test_every_entry_kind_is_a_timeline_entry(self):
        self._session(0, summary="x", content="y")
        ClientNote.objects.create(client=self.client_obj, note_date=date(2026, 3, 29), content="n")
        SupervisionItem.objects.create(client=self.client_obj, content="s")
        kinds = {
            re.search(r"cn-(session-row|note-item|supervision-item)", e).group(1)
            for e in self._entries(self._timeline())
        }
        self.assertEqual(kinds, {"session-row", "note-item", "supervision-item"})
