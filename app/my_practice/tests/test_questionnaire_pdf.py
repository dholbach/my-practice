"""
Tests for clinical questionnaire PDFs (P-118): content loader, PDF
generation with fillable fields, and the email-send view.
"""

import io
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase, override_settings
from django.urls import reverse
from my_practice.models import Client, Practice, UserPractice
from my_practice.utils.questionnaire_content import (
    QuestionnaireNotFoundError,
    load_questionnaire,
)
from my_practice.views.api_views import (
    _resolve_questionnaire_section,
    generate_questionnaire_pdf_bytes,
)

User = get_user_model()


class LoadQuestionnaireTest(TestCase):
    """Tests for the content loader (utils/questionnaire_content.py)."""

    def test_loads_shipped_gad7_fixture(self):
        content = load_questionnaire("gad7")
        self.assertEqual(content.code, "gad7")
        self.assertEqual(content.title["de"], "GAD-7 Fragebogen")
        self.assertEqual(content.title["en"], "GAD-7 Questionnaire")
        self.assertEqual(len(content.sections), 1)
        self.assertEqual(content.sections[0]["type"], "grid")
        self.assertEqual(len(content.sections[0]["items"]), 7)
        self.assertEqual(len(content.sections[0]["columns"]), 4)

    def test_missing_code_raises_actionable_error(self):
        with self.assertRaises(QuestionnaireNotFoundError) as ctx:
            load_questionnaire("does-not-exist")
        self.assertIn("does-not-exist", str(ctx.exception))

    def test_instance_local_file_takes_precedence_over_shipped_fixture(self):
        """PAYMENTS_DATA_DIR/questionnaires/gad7.json, if present, wins."""
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "questionnaires").mkdir()
            override_path = data_dir / "questionnaires" / "gad7.json"
            override_path.write_text(
                json.dumps(
                    {
                        "code": "gad7",
                        "title": {"de": "Override", "en": "Override"},
                        "intro": {},
                        "sections": [],
                    }
                ),
                encoding="utf-8",
            )
            with override_settings(PAYMENTS_DATA_DIR=data_dir):
                content = load_questionnaire("gad7")
        self.assertEqual(content.title["de"], "Override")


class QuestionnairePdfGenerationTest(TestCase):
    """Tests for generate_questionnaire_pdf_bytes / the questionnaire_pdf view."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="questionnaire-pdf-test",
            title="Test Practitioner",
            email="practice@example.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="qpdfuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_http = TestClient()
        self.client_http.login(username="qpdfuser", password="testpass123")

    def _get_form_fields(self, pdf_bytes: bytes) -> dict:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        return reader.get_fields() or {}

    def test_generate_bytes_returns_valid_pdf(self):
        pdf_bytes, filename = generate_questionnaire_pdf_bytes("gad7", self.practice, "de")
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertEqual(filename, "GAD7_de.pdf")

    def test_pdf_has_one_fillable_radio_group_per_item(self):
        """One radio-button group per statement (s0_q0..s0_q6), each with 4 choices."""
        pdf_bytes, _filename = generate_questionnaire_pdf_bytes("gad7", self.practice, "de")
        fields = self._get_form_fields(pdf_bytes)
        group_names = {name.split(".")[0] for name in fields}
        self.assertEqual(group_names, {f"s0_q{i}" for i in range(7)})

    def test_view_download_german_default(self):
        response = self.client_http.get(reverse("questionnaire_pdf", kwargs={"code": "gad7"}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("GAD7_de.pdf", response["Content-Disposition"])

    def test_view_lang_param_switches_to_english(self):
        response = self.client_http.get(
            reverse("questionnaire_pdf", kwargs={"code": "gad7"}) + "?lang=en"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("GAD7_en.pdf", response["Content-Disposition"])

    def test_view_unknown_code_redirects_with_error(self):
        response = self.client_http.get(
            reverse("questionnaire_pdf", kwargs={"code": "does-not-exist"})
        )
        self.assertRedirects(response, reverse("dashboard"))


class SendQuestionnairePdfEmailViewTest(TestCase):
    """Tests for SendQuestionnairePdfEmailView."""

    def setUp(self):
        import logging

        logging.getLogger("my_practice.email").setLevel(logging.ERROR)

        self.client_http = TestClient()
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="questionnaire-email-test",
            title="Test Practitioner",
            email="practice@test.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="qemailuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_http.login(username="qemailuser", password="testpass123")

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            email="max@example.com",
            practice=self.practice,
        )

    def test_form_loads_prefilled(self):
        response = self.client_http.get(
            reverse("send_questionnaire_pdf_email", kwargs={"pk": self.test_client.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/send_questionnaire_pdf_email.html")
        form = response.context["form"]
        self.assertEqual(form.initial["recipient"], "max@example.com")
        self.assertEqual(response.context["filename"], "GAD-7_de.pdf")

    def test_redirects_without_client_email(self):
        self.test_client.email = ""
        self.test_client.save()

        response = self.client_http.get(
            reverse("send_questionnaire_pdf_email", kwargs={"pk": self.test_client.pk})
        )
        self.assertRedirects(response, reverse("client_detail", kwargs={"pk": self.test_client.pk}))

    @patch("my_practice.views.email_views.EmailMessage")
    def test_send_attaches_pdf(self, mock_email):
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance
        mock_instance.send.return_value = 1

        response = self.client_http.post(
            reverse("send_questionnaire_pdf_email", kwargs={"pk": self.test_client.pk}),
            {
                "recipient": "max@example.com",
                "subject": "Fragebogen",
                "body": "Hallo",
            },
        )
        self.assertRedirects(response, reverse("client_detail", kwargs={"pk": self.test_client.pk}))
        mock_instance.send.assert_called_once()

        mock_instance.attach.assert_called_once()
        fname, fbytes, fmime = mock_instance.attach.call_args.args
        self.assertEqual(fname, "GAD-7_de.pdf")
        self.assertEqual(fmime, "application/pdf")
        self.assertTrue(fbytes.startswith(b"%PDF"))


class ResolveQuestionnaireSectionTest(TestCase):
    """Tests for _resolve_questionnaire_section (P-119: checklist + freetext)."""

    def test_grid_resolves_columns_and_field_names(self):
        section = {
            "type": "grid",
            "columns": [{"de": "Nie", "en": "Never"}, {"de": "Oft", "en": "Often"}],
            "items": [{"de": "Erstens", "en": "First"}, {"de": "Zweitens", "en": "Second"}],
        }
        resolved = _resolve_questionnaire_section(section, "de", index=2)
        self.assertEqual(resolved["type"], "grid")
        self.assertEqual(resolved["columns"], ["Nie", "Oft"])
        self.assertEqual(
            resolved["rows"],
            [
                {"label": "Erstens", "field_name": "s2_q0"},
                {"label": "Zweitens", "field_name": "s2_q1"},
            ],
        )

    def test_checklist_resolves_items_and_field_names(self):
        section = {
            "type": "checklist",
            "items": [{"de": "Scheidung", "en": "Divorce"}, {"de": "Umzug", "en": "Moving"}],
        }
        resolved = _resolve_questionnaire_section(section, "en", index=0)
        self.assertEqual(resolved["type"], "checklist")
        self.assertEqual(
            resolved["rows"],
            [
                {"label": "Divorce", "field_name": "s0_c0"},
                {"label": "Moving", "field_name": "s0_c1"},
            ],
        )

    def test_freetext_resolves_field_names_for_line_count(self):
        section = {
            "type": "freetext",
            "intro": {"de": "Bitte angeben:", "en": "Please indicate:"},
            "lines": 2,
        }
        resolved = _resolve_questionnaire_section(section, "en", index=3)
        self.assertEqual(resolved["type"], "freetext")
        self.assertEqual(resolved["intro"], "Please indicate:")
        self.assertEqual(resolved["field_names"], ["s3_f0", "s3_f1"])

    def test_freetext_defaults_to_one_line(self):
        resolved = _resolve_questionnaire_section({"type": "freetext"}, "de", index=0)
        self.assertEqual(resolved["field_names"], ["s0_f0"])

    def test_unknown_type_raises_value_error(self):
        with self.assertRaises(ValueError):
            _resolve_questionnaire_section({"type": "essay"}, "de", index=0)


class MixedSectionQuestionnairePdfTest(TestCase):
    """End-to-end test: a document mixing grid + checklist + freetext sections."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="mixed-questionnaire-test",
            title="Test Practitioner",
            email="practice@example.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="mixeduser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)

    def _get_form_fields(self, pdf_bytes: bytes) -> dict:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        return reader.get_fields() or {}

    def test_mixed_content_renders_all_field_types(self):
        import json
        import tempfile
        from pathlib import Path

        content = {
            "code": "mixed-test",
            "title": {"de": "Testbogen", "en": "Test Form"},
            "intro": {"de": "", "en": ""},
            "sections": [
                {
                    "type": "checklist",
                    "items": [{"de": "Ereignis A", "en": "Event A"}],
                },
                {
                    "type": "freetext",
                    "lines": 2,
                },
                {
                    "type": "grid",
                    "columns": [{"de": "Nie", "en": "Never"}, {"de": "Oft", "en": "Often"}],
                    "items": [{"de": "Aussage 1", "en": "Statement 1"}],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "questionnaires").mkdir()
            (data_dir / "questionnaires" / "mixed-test.json").write_text(
                json.dumps(content), encoding="utf-8"
            )
            with override_settings(PAYMENTS_DATA_DIR=data_dir):
                pdf_bytes, filename = generate_questionnaire_pdf_bytes(
                    "mixed-test", self.practice, "de"
                )

        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertEqual(filename, "MIXED-TEST_de.pdf")

        fields = self._get_form_fields(pdf_bytes)
        field_names = set(fields)
        self.assertIn("s0_c0", field_names)  # checklist checkbox
        self.assertIn("s1_f0", field_names)  # freetext line 1
        self.assertIn("s1_f1", field_names)  # freetext line 2
        self.assertIn(
            "s2_q0.s2_q0", field_names
        )  # grid radio group (nested naming, see GAD-7 test)
