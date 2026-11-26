"""The case sheet (P-006 PR 4): lines, versions, views, the page, and the migration that fills it."""

import importlib
from datetime import date
from decimal import Decimal

from django.apps import apps
from django.db import connection
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from ..models import Client, ClientProfile, ClinicalFact, Session, SessionLog
from ..models.case_sheet import CASE_SHEET_ROWS, ROWS_BY_KIND, cell_keys
from ..utils.case_sheet import (
    add_line,
    build_case_sheet,
    change_line,
    clean_content,
    describe_fact,
    resolve_line,
    valid_cell,
    working_diagnosis,
)
from .test_clinical import TEST_FERNET_KEY, ClinicalTestBase
from .test_helpers import create_test_practice

migration = importlib.import_module("my_practice.migrations.0019_split_profile_notes_into_facts")


class SheetDefinitionTests(SimpleTestCase):
    def test_kinds_are_unique_and_fit_the_column(self):
        kinds = [row.kind for row in CASE_SHEET_ROWS]
        self.assertEqual(len(kinds), len(set(kinds)))
        self.assertTrue(all(len(kind) <= 30 for kind in kinds))

    def test_cell_keys_are_unique_within_a_row_and_fit_the_column(self):
        for row in CASE_SHEET_ROWS:
            keys = cell_keys(row)
            self.assertEqual(len(keys), len(set(keys)), row.kind)
            self.assertTrue(all(len(key) <= 30 for key in keys), row.kind)

    def test_a_row_without_cells_has_one_cell_with_an_empty_key(self):
        self.assertEqual(cell_keys(ROWS_BY_KIND["concern"]), ("",))
        self.assertEqual(cell_keys(ROWS_BY_KIND["symptoms"]), ("onset", "change", "until"))

    def test_valid_cell(self):
        self.assertTrue(valid_cell("concern", ""))
        self.assertTrue(valid_cell("symptoms", "onset"))
        self.assertFalse(valid_cell("symptoms", ""))  # a row with cells needs one
        self.assertFalse(valid_cell("concern", "onset"))
        self.assertFalse(valid_cell("nope", ""))

    def test_the_migration_only_uses_kinds_and_cells_the_sheet_has(self):
        for kind, labels in migration.INTAKE_HEADINGS.values():
            self.assertIn(kind, ROWS_BY_KIND)
            for key in labels.values():
                self.assertIn(key, cell_keys(ROWS_BY_KIND[kind]), kind)
        self.assertLessEqual(migration.MULTI_KINDS, set(ROWS_BY_KIND))
        for kind in migration.MULTI_KINDS:
            self.assertTrue(ROWS_BY_KIND[kind].multi, kind)

    def test_clean_content(self):
        self.assertEqual(clean_content("  a\nb \n"), "a\nb")
        self.assertEqual(len(clean_content("x" * 9000)), 5000)


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class LineOperationsTests(ClinicalTestBase):
    def _lines(self, kind, sub=""):
        return list(
            ClinicalFact.objects.filter(client=self.client_obj, kind=kind, sub=sub).order_by("pk")
        )

    def test_add_creates_a_dated_active_line(self):
        fact = add_line(self.client_obj, "resources", "", "  Hund ", today=date(2026, 3, 1))
        self.assertEqual(
            (fact.content, fact.noted_on, fact.status, fact.closed_on),
            ("Hund", date(2026, 3, 1), "active", None),
        )

    def test_a_multi_row_keeps_every_line(self):
        add_line(self.client_obj, "resources", "", "Hund")
        add_line(self.client_obj, "resources", "", "Wald")
        self.assertEqual([f.status for f in self._lines("resources")], ["active", "active"])

    def test_a_single_cell_supersedes_the_current_line(self):
        first = add_line(self.client_obj, "hypothesis", "", "alt", today=date(2026, 3, 1))
        second = add_line(self.client_obj, "hypothesis", "", "neu", today=date(2026, 4, 1))
        first.refresh_from_db()
        self.assertEqual(
            (first.status, first.closed_on, first.superseded_by),
            ("superseded", date(2026, 4, 1), second),
        )
        self.assertEqual(second.status, "active")

    def test_sub_cells_of_one_row_do_not_supersede_each_other(self):
        add_line(self.client_obj, "symptoms", "onset", "Frühjahr")
        add_line(self.client_obj, "symptoms", "change", "seit Teamwechsel")
        self.assertEqual(
            {
                f.status
                for f in ClinicalFact.objects.filter(client=self.client_obj, kind="symptoms")
            },
            {"active"},
        )

    def test_add_ignores_empty_text_and_unknown_cells(self):
        self.assertIsNone(add_line(self.client_obj, "resources", "", "   "))
        self.assertIsNone(add_line(self.client_obj, "nope", "", "x"))
        self.assertIsNone(add_line(self.client_obj, "symptoms", "", "x"))
        self.assertFalse(ClinicalFact.objects.exists())

    def test_add_records_the_source_session(self):
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), duration=60
        )
        fact = add_line(self.client_obj, "resources", "", "Hund", source_session=session)
        self.assertEqual(fact.source_session, session)

    def test_change_supersedes_with_a_new_line_in_the_same_cell(self):
        old = add_line(self.client_obj, "resources", "", "Hund", today=date(2026, 3, 1))
        new = change_line(old, "Hund und Bruder", today=date(2026, 4, 1))
        old.refresh_from_db()
        self.assertEqual(
            (new.kind, new.sub, new.content, new.noted_on),
            ("resources", "", "Hund und Bruder", date(2026, 4, 1)),
        )
        self.assertEqual(
            (old.status, old.superseded_by, old.closed_on), ("superseded", new, date(2026, 4, 1))
        )
        self.assertEqual(old.content, "Hund")  # the earlier wording is kept

    def test_change_keeps_the_source_session(self):
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), duration=60
        )
        old = add_line(self.client_obj, "resources", "", "Hund", source_session=session)
        self.assertEqual(change_line(old, "Hund, Wald").source_session, session)

    def test_change_does_nothing_for_empty_unchanged_or_closed_lines(self):
        line = add_line(self.client_obj, "resources", "", "Hund")
        self.assertIsNone(change_line(line, "  "))
        self.assertIsNone(change_line(line, "Hund "))
        resolve_line(line)
        self.assertIsNone(change_line(line, "etwas anderes"))
        self.assertEqual(ClinicalFact.objects.count(), 1)

    def test_resolve_closes_the_line_and_keeps_it(self):
        line = add_line(self.client_obj, "current_triggers", "", "Telefon")
        self.assertTrue(resolve_line(line, today=date(2026, 5, 1)))
        line.refresh_from_db()
        self.assertEqual(
            (line.status, line.closed_on, line.content), ("resolved", date(2026, 5, 1), "Telefon")
        )
        self.assertFalse(resolve_line(line))  # already closed

    def test_working_diagnosis_is_the_current_diagnosis_line(self):
        self.assertEqual(working_diagnosis(self.client_obj), "")
        add_line(self.client_obj, "diagnosis", "", "F43.2")
        self.assertEqual(working_diagnosis(self.client_obj), "F43.2")
        add_line(self.client_obj, "diagnosis", "", "F43.1")
        self.assertEqual(working_diagnosis(self.client_obj), "F43.1")

    def test_content_is_encrypted_at_rest(self):
        add_line(self.client_obj, "hypothesis", "", "sensitive wording")
        with connection.cursor() as cursor:
            cursor.execute("SELECT content FROM my_practice_clinicalfact")
            self.assertNotIn("sensitive", cursor.fetchone()[0])


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class BuildCaseSheetTests(ClinicalTestBase):
    def test_every_row_is_there_in_sheet_order_even_when_empty(self):
        rows = build_case_sheet(self.client_obj)
        self.assertEqual([r.row.kind for r in rows], [r.kind for r in CASE_SHEET_ROWS])
        self.assertTrue(all(not cell.lines and not cell.history for r in rows for cell in r.cells))

    def test_cells_carry_labels_lines_and_history_newest_first(self):
        first = add_line(self.client_obj, "symptoms", "onset", "v1", today=date(2026, 1, 1))
        second = change_line(first, "v2", today=date(2026, 2, 1))
        change_line(second, "v3", today=date(2026, 3, 1))
        row = next(r for r in build_case_sheet(self.client_obj) if r.row.kind == "symptoms")
        self.assertTrue(row.has_cells)
        onset = next(c for c in row.cells if c.key == "onset")
        self.assertEqual(onset.label, "Beginn")
        self.assertEqual([f.content for f in onset.lines], ["v3"])
        self.assertEqual(onset.current.content, "v3")
        self.assertEqual([f.content for f in onset.history], ["v2", "v1"])
        self.assertEqual(next(c for c in row.cells if c.key == "until").current, None)

    def test_other_clients_lines_never_appear(self):
        other = Client.objects.create(
            client_code="XX-9",
            full_name="Max Mustermann",
            email="max@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        add_line(other, "resources", "", "theirs")
        rows = build_case_sheet(self.client_obj)
        self.assertEqual([c.lines for r in rows for c in r.cells if c.lines], [])


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class DescribeFactTests(ClinicalTestBase):
    def test_labels_of_row_and_cell(self):
        fact = add_line(self.client_obj, "symptoms", "onset", "Seit dem Frühjahr")
        self.assertEqual(
            describe_fact(fact),
            {"row": "Symptomatik", "cell": "Beginn", "content": "Seit dem Frühjahr"},
        )

    def test_single_cell_row_has_no_cell_label(self):
        fact = add_line(self.client_obj, "concern", "", "x")
        self.assertEqual(describe_fact(fact)["cell"], "")

    def test_row_that_left_the_sheet_shows_its_kind(self):
        fact = ClinicalFact(kind="gone_row", sub="", content="old")
        self.assertEqual(describe_fact(fact), {"row": "gone_row", "cell": "", "content": "old"})

    def test_working_diagnosis_from_a_built_sheet_runs_no_query(self):
        add_line(self.client_obj, "diagnosis", "", "F43.1")
        sheet = build_case_sheet(self.client_obj)
        with self.assertNumQueries(0):
            self.assertEqual(working_diagnosis(self.client_obj, sheet=sheet), "F43.1")
        self.assertEqual(working_diagnosis(self.client_obj), "F43.1")


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class CaseSheetViewTests(ClinicalTestBase):
    def _url(self, name, *args):
        return reverse(name, args=[self.client_obj.pk, *args])

    def test_add_creates_a_line_and_returns_to_its_row(self):
        response = self.http.post(
            self._url("case_fact_add"), {"kind": "resources", "sub": "", "content": " Hund "}
        )
        self.assertEqual(ClinicalFact.objects.get().content, "Hund")
        self.assertTrue(response.url.endswith("#case-row-resources"))

    def test_add_to_a_single_cell_replaces_the_line(self):
        for text in ("alt", "neu"):
            self.http.post(
                self._url("case_fact_add"), {"kind": "hypothesis", "sub": "", "content": text}
            )
        self.assertEqual(
            [(f.content, f.status) for f in ClinicalFact.objects.order_by("pk")],
            [("alt", "superseded"), ("neu", "active")],
        )

    def test_add_rejects_empty_text_and_unknown_cells(self):
        self.http.post(self._url("case_fact_add"), {"kind": "resources", "sub": "", "content": " "})
        self.http.post(self._url("case_fact_add"), {"kind": "bogus", "sub": "", "content": "x"})
        self.http.post(self._url("case_fact_add"), {"kind": "symptoms", "sub": "", "content": "x"})
        self.assertFalse(ClinicalFact.objects.exists())

    def test_update_rewords_through_a_new_line(self):
        line = add_line(self.client_obj, "resources", "", "Hund")
        response = self.http.post(self._url("case_fact_update", line.pk), {"content": "Hund, Wald"})
        line.refresh_from_db()
        self.assertEqual(line.status, "superseded")
        self.assertEqual(line.superseded_by.content, "Hund, Wald")
        self.assertTrue(response.url.endswith("#case-row-resources"))

    def test_update_with_empty_text_changes_nothing(self):
        line = add_line(self.client_obj, "resources", "", "Hund")
        self.http.post(self._url("case_fact_update", line.pk), {"content": "  "})
        line.refresh_from_db()
        self.assertEqual((line.status, ClinicalFact.objects.count()), ("active", 1))

    def test_resolve_marks_the_line_and_keeps_it(self):
        line = add_line(self.client_obj, "current_triggers", "", "Telefon")
        self.http.post(self._url("case_fact_resolve", line.pk))
        line.refresh_from_db()
        self.assertEqual(line.status, "resolved")

    def test_views_only_accept_post(self):
        line = add_line(self.client_obj, "resources", "", "Hund")
        for name, args in (
            ("case_fact_add", ()),
            ("case_fact_update", (line.pk,)),
            ("case_fact_resolve", (line.pk,)),
        ):
            self.assertEqual(self.http.get(self._url(name, *args)).status_code, 405, name)

    def test_follows_a_safe_next_only(self):
        response = self.http.post(
            self._url("case_fact_add"),
            {"kind": "resources", "sub": "", "content": "a", "next": "https://evil.example/"},
        )
        self.assertTrue(response.url.startswith("/clients/"))

    def test_another_practices_client_and_foreign_lines_are_404(self):
        other_practice = create_test_practice(
            name="Other", slug="other-sheet", email="o@practice.example"
        )
        other_client = Client.objects.create(
            client_code="XX-9",
            full_name="Max Mustermann",
            email="max@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=other_practice,
        )
        foreign = add_line(other_client, "resources", "", "theirs")
        urls = [
            reverse("case_fact_add", args=[other_client.pk]),
            reverse("case_fact_update", args=[other_client.pk, foreign.pk]),
            reverse("case_fact_resolve", args=[other_client.pk, foreign.pk]),
        ]
        for url in urls:
            self.assertEqual(
                self.http.post(url, {"kind": "resources", "sub": "", "content": "x"}).status_code,
                404,
            )
        foreign.refresh_from_db()
        self.assertEqual((foreign.status, ClinicalFact.objects.count()), ("active", 1))

    def test_a_line_of_another_client_cannot_be_reached_through_this_one(self):
        other = Client.objects.create(
            client_code="XX-8",
            full_name="Anna Schmidt",
            email="anna2@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        foreign = add_line(other, "resources", "", "theirs")
        self.assertEqual(
            self.http.post(self._url("case_fact_update", foreign.pk), {"content": "x"}).status_code,
            404,
        )
        self.assertEqual(
            self.http.post(self._url("case_fact_resolve", foreign.pk)).status_code, 404
        )

    def test_deleting_the_client_deletes_its_lines(self):
        add_line(self.client_obj, "resources", "", "Hund")
        self.client_obj.delete()
        self.assertFalse(ClinicalFact.objects.exists())


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class CaseSheetPageTests(ClinicalTestBase):
    def _html(self):
        return self.http.get(
            reverse("client_detail", kwargs={"pk": self.client_obj.pk})
        ).content.decode()

    def test_the_page_shows_every_row_with_its_label(self):
        html = self._html()
        self.assertIn('id="case-sheet"', html)
        for row in CASE_SHEET_ROWS:
            self.assertIn(f'id="case-row-{row.kind}"', html, row.kind)
            self.assertIn(row.label, html, row.kind)
        self.assertIn("Beginn", html)  # a sub-cell label

    def test_lines_show_with_their_date_and_an_edit_form(self):
        line = add_line(self.client_obj, "resources", "", "Hund", today=date(2026, 3, 1))
        html = self._html()
        self.assertIn("Hund", html)
        self.assertIn("01.03.26", html)
        self.assertIn(reverse("case_fact_update", args=[self.client_obj.pk, line.pk]), html)
        self.assertIn(reverse("case_fact_resolve", args=[self.client_obj.pk, line.pk]), html)

    def test_a_multi_row_always_offers_adding_but_a_filled_single_cell_does_not(self):
        add_line(self.client_obj, "resources", "", "Hund")
        add_line(self.client_obj, "hypothesis", "", "Übererregung")
        html = self._html()
        resources = html.split('id="case-row-resources"')[1].split('id="case-row-', 1)[0]
        hypothesis = html.split('id="case-row-hypothesis"')[1].split('id="case-row-', 1)[0]
        self.assertIn('class="cs-add"', resources)
        self.assertNotIn('class="cs-add"', hypothesis)
        self.assertIn('class="cs-edit"', hypothesis)

    def test_earlier_versions_are_listed_under_the_cell(self):
        line = add_line(self.client_obj, "hypothesis", "", "erste Fassung", today=date(2026, 1, 1))
        change_line(line, "zweite Fassung", today=date(2026, 2, 1))
        row = self._html().split('id="case-row-hypothesis"')[1].split('id="case-row-', 1)[0]
        self.assertIn("cs-history", row)
        self.assertIn("erste Fassung", row)
        self.assertIn("zweite Fassung", row)

    def test_a_line_added_from_a_log_links_to_that_log(self):
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), duration=60
        )
        log = SessionLog.objects.create(session=session, content="x")
        add_line(self.client_obj, "resources", "", "Hund", source_session=session)
        self.assertIn(
            reverse("session_log_edit", kwargs={"client_pk": self.client_obj.pk, "log_pk": log.pk}),
            self._html().split('id="case-row-resources"')[1].split('id="case-row-', 1)[0],
        )

    def test_the_diagnosis_shows_in_the_header_and_the_stat_card(self):
        add_line(self.client_obj, "diagnosis", "", "F43.2 Anpassungsstörung")
        html = self._html()
        self.assertGreaterEqual(html.count("F43.2 Anpassungsstörung"), 3)  # header, stat card, row

    def test_the_old_profile_form_is_gone(self):
        html = self._html()
        self.assertNotIn("client-profile-form", html)
        self.assertNotIn('name="intake_notes"', html)

    def test_previous_notes_show_read_only_only_when_there_are_some(self):
        self.assertNotIn("cs-legacy", self._html())
        ClientProfile.objects.create(client=self.client_obj, intake_notes="## Anliegen\nSchlaf")
        html = self._html()
        self.assertIn("cs-legacy", html)
        self.assertNotIn("<textarea", html.split("cs-legacy")[1].split("</details>")[0])

    def test_opening_the_page_does_not_create_a_profile(self):
        self._html()
        self.assertFalse(ClientProfile.objects.filter(client=self.client_obj).exists())

    def test_the_missing_diagnosis_callout_points_at_the_diagnosis_row(self):
        self.client_obj.needs_gebueh_invoice = True
        self.client_obj.save()
        self.assertIn('href="#case-row-diagnosis"', self._html())
        add_line(self.client_obj, "diagnosis", "", "F43.2")
        self.assertNotIn('href="#case-row-diagnosis"', self._html())


class LegacySplitTests(SimpleTestCase):
    """The pure parser of the migration that fills the sheet from the old notes."""

    def _split(self, intake="", case="", diagnosis=""):
        return migration.legacy_to_facts(intake, case, diagnosis)

    def test_a_filled_section_becomes_a_line_of_its_row(self):
        self.assertEqual(self._split("## Anliegen\nSchlaf\n"), [("concern", "", "Schlaf")])

    def test_empty_sections_and_label_only_lines_are_dropped(self):
        text = "## Anliegen\n\n## Symptomatik\n**Beginn:**\n**Dauer bis:**\n\n## Körperlich\n   \n"
        self.assertEqual(self._split(text), [])

    def test_labelled_values_go_to_their_cells(self):
        text = "## Symptomatik\n**Beginn:** Frühjahr 2025\n**Verschlimmerung/Änderung:**\nseit Teamwechsel\nund Umzug\n**Dauer bis:**\n"
        self.assertEqual(
            self._split(text),
            [
                ("symptoms", "onset", "Frühjahr 2025"),
                ("symptoms", "change", "seit Teamwechsel\nund Umzug"),
            ],
        )

    def test_label_spellings_are_matched_loosely(self):
        text = "## Nervensystem / ANS\n**Erregungslage / Grundmuster:** hoch\n## Limbisches System\n**Loyalität/Scham/Schuld:** viel\n"
        self.assertEqual(
            self._split(text), [("ans", "arousal", "hoch"), ("limbic", "loyalty", "viel")]
        )

    def test_text_next_to_unknown_labels_is_kept_as_a_note_with_its_heading(self):
        text = "## Symptomatik\n**Beginn:** 2025\n**Schweregrad:** hoch\n"
        self.assertEqual(
            self._split(text),
            [("symptoms", "onset", "2025"), ("notes", "", "## Symptomatik\n**Schweregrad:** hoch")],
        )

    def test_bullets_in_a_multi_row_become_separate_lines(self):
        text = "## Aktuelle Trigger\n- laute Stimmen\n- Telefon\n  klingelt oft\n* Zeitdruck\n"
        self.assertEqual(
            self._split(text),
            [
                ("current_triggers", "", "laute Stimmen"),
                ("current_triggers", "", "Telefon\nklingelt oft"),
                ("current_triggers", "", "Zeitdruck"),
            ],
        )

    def test_bullets_in_a_single_row_stay_one_line(self):
        text = "## Arbeitshypothese\n- a\n- b\n"
        self.assertEqual(self._split(text), [("hypothesis", "", "- a\n- b")])

    def test_prose_in_a_multi_row_stays_one_line(self):
        text = "## Ressourcen\nWald, Hund\nund ein Bruder\n"
        self.assertEqual(self._split(text), [("resources", "", "Wald, Hund\nund ein Bruder")])

    def test_case_notes_headings_are_known_too(self):
        text = "## Themen\n- Kontrolle\n## Familiendynamik\nÄltester\n## Zukünftige Arbeit / Fragen\nTitration\n"
        self.assertEqual(
            self._split("", text),
            [
                ("themes", "", "Kontrolle"),
                ("family", "", "Ältester"),
                ("future_work", "", "Titration"),
            ],
        )

    def test_headings_match_with_quotes_case_and_spacing_differences(self):
        text = '## "Sicherheit" gestört durch\nLärm\n## ERST-AUSLÖSER\nUnfall\n## Therapieziel (Patient)\nAbschalten\n'
        self.assertEqual(
            self._split(text),
            [("safety", "", "Lärm"), ("first_trigger", "", "Unfall"), ("goal", "", "Abschalten")],
        )

    def test_unknown_headings_the_old_course_section_and_preamble_become_notes(self):
        text = "Vorab etwas\n## Verlauf\nErste Sitzung gut\n## Neue Überschrift\nText\n"
        self.assertEqual(
            self._split(text),
            [
                ("notes", "", "Vorab etwas"),
                ("notes", "", "## Verlauf\nErste Sitzung gut"),
                ("notes", "", "## Neue Überschrift\nText"),
            ],
        )

    def test_the_diagnosis_field_wins_over_the_section(self):
        self.assertEqual(
            self._split("## Arbeitsdiagnose\nF43.2\n", diagnosis="F43.2"),
            [("diagnosis", "", "F43.2")],
        )
        self.assertEqual(
            self._split("## Arbeitsdiagnose\nalt\n", diagnosis="F43.2"),
            [("diagnosis", "", "F43.2"), ("notes", "", "## Arbeitsdiagnose\nalt")],
        )

    def test_the_section_is_used_when_the_field_is_empty(self):
        self.assertEqual(self._split("## Arbeitsdiagnose\nF43.2\n"), [("diagnosis", "", "F43.2")])

    def test_empty_input(self):
        self.assertEqual(self._split("", "", ""), [])
        self.assertEqual(self._split(None, None, None), [])


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class LegacySplitMigrationTests(ClinicalTestBase):
    """The data step itself, run against the real models."""

    def _profile(self, **fields):
        return ClientProfile.objects.create(client=self.client_obj, **fields)

    def _run(self):
        migration.split_profiles(apps, None)

    def test_a_profile_is_split_into_lines_dated_with_its_last_save(self):
        profile = self._profile(
            intake_notes="## Anliegen\nSchlaf",
            case_notes="## Themen\n- Kontrolle",
            arbeitsdiagnose="F43.2",
        )
        self._run()
        facts = list(ClinicalFact.objects.filter(client=self.client_obj).order_by("pk"))
        self.assertEqual(
            [(f.kind, f.sub, f.content) for f in facts],
            [("diagnosis", "", "F43.2"), ("concern", "", "Schlaf"), ("themes", "", "Kontrolle")],
        )
        self.assertTrue(
            all(f.noted_on == profile.updated_at.date() and f.status == "active" for f in facts)
        )

    def test_the_old_fields_are_left_untouched(self):
        self._profile(intake_notes="## Anliegen\nSchlaf", arbeitsdiagnose="F43.2")
        self._run()
        profile = ClientProfile.objects.get()
        self.assertEqual(
            (profile.intake_notes, profile.arbeitsdiagnose), ("## Anliegen\nSchlaf", "F43.2")
        )

    def test_running_it_twice_does_not_duplicate_lines(self):
        self._profile(intake_notes="## Anliegen\nSchlaf")
        self._run()
        self._run()
        self.assertEqual(ClinicalFact.objects.count(), 1)

    def test_a_client_who_already_has_lines_is_skipped(self):
        add_line(self.client_obj, "resources", "", "Hund")
        self._profile(intake_notes="## Anliegen\nSchlaf")
        self._run()
        self.assertEqual(ClinicalFact.objects.count(), 1)

    def test_an_empty_profile_makes_no_lines(self):
        self._profile()
        self._run()
        self.assertFalse(ClinicalFact.objects.exists())
