"""The "anything for the case sheet?" step after saving a log (P-006 PR 5)."""

from datetime import date
from decimal import Decimal

from django.contrib.messages import get_messages
from django.test import override_settings
from django.urls import reverse

from ..models import Client, ClinicalFact, Session, SessionLog
from ..models.case_sheet import CASE_SHEET_ROWS, cell_keys
from ..utils.case_sheet import add_line
from .test_clinical import TEST_FERNET_KEY, ClinicalTestBase


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class DigestStepTests(ClinicalTestBase):
    def setUp(self):
        super().setUp()
        self.session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), duration=60
        )
        self.log = SessionLog.objects.create(session=self.session, content="x", summary="s")

    def _detail_url(self):
        return reverse("client_detail", kwargs={"pk": self.client_obj.pk})

    def _card(self, query=None):
        query = {"digest": self.session.pk} if query is None else query
        html = self.http.get(self._detail_url(), query).content.decode()
        return html, ('id="digest-card"' in html)

    def _add_url(self):
        return reverse("case_fact_add", kwargs={"pk": self.client_obj.pk})

    # ── getting to the card ──

    def test_saving_a_new_log_lands_on_the_card_for_that_session(self):
        response = self.http.post(
            reverse("session_log_create", kwargs={"pk": self.client_obj.pk}),
            {"session_date": "2026-03-27", "content": "x"},
        )
        session = Session.objects.get(session_date=date(2026, 3, 27))
        self.assertEqual(response.url, f"{self._detail_url()}?digest={session.pk}#digest-card")

    def test_saving_an_edited_log_does_not_open_the_card(self):
        response = self.http.post(
            reverse(
                "session_log_edit",
                kwargs={"client_pk": self.client_obj.pk, "log_pk": self.log.pk},
            ),
            {"content": "changed"},
        )
        self.assertNotIn("digest", response.url)

    def test_a_logged_session_row_links_to_its_card(self):
        html, _ = self._card(query={})
        self.assertIn(f"?digest={self.session.pk}#digest-card", html)

    # ── the card ──

    def test_no_card_without_the_parameter(self):
        self.assertFalse(self._card(query={})[1])

    def test_the_card_names_the_session_and_posts_to_the_case_sheet(self):
        html, shown = self._card()
        self.assertTrue(shown)
        card = html.split('id="digest-card"')[1].split("</form>")[0]
        self.assertIn("20.03.2026", card)
        self.assertIn(f'name="source_session" value="{self.session.pk}"', card)
        self.assertIn(self._add_url(), card)
        self.assertIn(
            f"?digest={self.session.pk}#digest-card", card
        )  # the next page keeps the card

    def test_the_picker_offers_every_cell_of_the_sheet(self):
        html, _ = self._card()
        picker = html.split('id="digest-target"')[1].split("</select>")[0]
        expected = sum(len(cell_keys(row)) for row in CASE_SHEET_ROWS)
        self.assertEqual(picker.count("<option"), expected)
        self.assertIn('value="symptoms|onset"', picker)
        self.assertIn('value="resources|"', picker)

    def test_a_filled_single_cell_says_it_replaces_the_current_line(self):
        add_line(self.client_obj, "hypothesis", "", "Übererregung")
        add_line(self.client_obj, "resources", "", "Hund")
        picker = self._card()[0].split('id="digest-target"')[1].split("</select>")[0]
        hypothesis = picker.split('value="hypothesis|"')[1].split("</option>")[0]
        resources = picker.split('value="resources|"')[1].split("</option>")[0]
        self.assertIn("(", hypothesis)
        self.assertNotIn("(", resources)

    def test_bad_session_values_show_no_card(self):
        other = Client.objects.create(
            client_code="XX-9",
            full_name="Max Mustermann",
            email="max@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        foreign = Session.objects.create(client=other, session_date=date(2026, 3, 21), duration=60)
        for value in ("abc", "", "99999999", str(foreign.pk), "-1"):
            self.assertFalse(self._card(query={"digest": value})[1], value)

    def test_lines_added_from_the_session_are_listed_on_the_card(self):
        add_line(self.client_obj, "resources", "", "Hund", source_session=self.session)
        add_line(self.client_obj, "symptoms", "onset", "Frühjahr", source_session=self.session)
        add_line(self.client_obj, "resources", "", "from elsewhere")
        card = self._card()[0].split('id="digest-card"')[1].split("</form>")[0]
        self.assertIn("Hund", card)
        self.assertIn("Symptomatik › Beginn", card)
        self.assertNotIn("from elsewhere", card)

    # ── adding a line ──

    def _add(self, **post):
        return self.http.post(self._add_url(), post)

    def test_a_line_from_the_card_records_its_session_and_returns_to_the_card(self):
        response = self._add(
            target="resources|",
            content="Hund",
            source_session=self.session.pk,
            next=f"{self._detail_url()}?digest={self.session.pk}#digest-card",
        )
        fact = ClinicalFact.objects.get()
        self.assertEqual(
            (fact.kind, fact.sub, fact.content, fact.source_session),
            ("resources", "", "Hund", self.session),
        )
        self.assertEqual(response.url, f"{self._detail_url()}?digest={self.session.pk}#digest-card")

    def test_adding_confirms_with_a_message(self):
        response = self._add(target="resources|", content="Hund", source_session=self.session.pk)
        self.assertEqual(len(list(get_messages(response.wsgi_request))), 1)

    def test_a_cell_with_a_sub_part_is_addressed_with_the_bar(self):
        self._add(target="symptoms|onset", content="Frühjahr", source_session=self.session.pk)
        fact = ClinicalFact.objects.get()
        self.assertEqual((fact.kind, fact.sub), ("symptoms", "onset"))

    def test_a_single_cell_is_replaced_and_the_old_line_kept(self):
        add_line(self.client_obj, "hypothesis", "", "alt")
        self._add(target="hypothesis|", content="neu", source_session=self.session.pk)
        self.assertEqual(
            [(f.content, f.status) for f in ClinicalFact.objects.order_by("pk")],
            [("alt", "superseded"), ("neu", "active")],
        )

    def test_several_lines_can_be_added_one_after_the_other(self):
        for text in ("Hund", "Wald"):
            self._add(target="resources|", content=text, source_session=self.session.pk)
        self.assertEqual(ClinicalFact.objects.filter(source_session=self.session).count(), 2)

    def test_an_unknown_target_or_empty_line_adds_nothing(self):
        self._add(target="bogus|", content="x", source_session=self.session.pk)
        self._add(target="symptoms|", content="x", source_session=self.session.pk)
        self._add(target="resources|", content="  ", source_session=self.session.pk)
        self.assertFalse(ClinicalFact.objects.exists())

    def test_a_session_of_another_client_is_not_recorded_as_the_source(self):
        other = Client.objects.create(
            client_code="XX-9",
            full_name="Max Mustermann",
            email="max@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        foreign = Session.objects.create(client=other, session_date=date(2026, 3, 21), duration=60)
        self._add(target="resources|", content="Hund", source_session=foreign.pk)
        self.assertIsNone(ClinicalFact.objects.get().source_session)

    def test_the_old_kind_and_sub_form_still_works_without_a_session(self):
        response = self._add(kind="resources", sub="", content="Hund")
        fact = ClinicalFact.objects.get()
        self.assertIsNone(fact.source_session)
        self.assertEqual(
            len(list(get_messages(response.wsgi_request))), 0
        )  # the sheet's own forms stay quiet

    def test_the_line_shows_on_the_sheet_with_a_link_to_the_session(self):
        self._add(target="resources|", content="Hund", source_session=self.session.pk)
        html = self.http.get(self._detail_url()).content.decode()
        row = html.split('id="case-row-resources"')[1].split('id="case-row-', 1)[0]
        self.assertIn(
            reverse(
                "session_log_edit", kwargs={"client_pk": self.client_obj.pk, "log_pk": self.log.pk}
            ),
            row,
        )
