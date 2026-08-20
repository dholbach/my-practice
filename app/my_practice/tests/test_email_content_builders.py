"""
Tests for the email content builders in utils/email_utils.py.

These build the subject and body text that actually reaches a client. They sit
in a double blind spot: the i18n coverage guardrail deliberately exempts them
(they are authored bilingual content, not Django-i18n UI chrome — see CLAUDE.md),
and test_email_views.py mocks the send, so it asserts that an email went out but
never what it said.

Every builder is therefore exercised here under *both* client languages, with
assertions on distinguishing content rather than "is a non-empty string" — a
German assertion that would also pass against the English branch tests nothing.
"""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from my_practice.models import (
    Client,
    Invoice,
    InvoiceItem,
    Practice,
    ServiceType,
    Session,
    TimeOff,
)
from my_practice.utils.email_utils import (
    get_contract_email_content,
    get_gdpr_deletion_email_content,
    get_intake_email_content,
    get_invoice_email_content,
    get_questionnaire_email_content,
    get_questionnaire_pdf_email_content,
    get_salutation_for_client,
    get_timeoff_notice_default_content,
    prepare_invoice_email_context,
    render_email_template,
)
from my_practice.utils.formatting import format_currency_de
from my_practice.validators import validate_email_template_placeholders

NBSP = "\u00a0"  # explicit: an invisible literal here is too easy to "tidy away"


class FormatCurrencyDeTest(TestCase):
    """format_currency_de is the single definition of how money is written."""

    def test_german_separators(self):
        self.assertEqual(format_currency_de(Decimal("11064.03")), f"11.064,03{NBSP}€")

    def test_uses_non_breaking_space(self):
        # A regular space would let the amount wrap away from its symbol.
        self.assertIn(NBSP, format_currency_de(Decimal("100.00")))
        self.assertNotIn(" €", format_currency_de(Decimal("100.00")))

    def test_always_two_decimals(self):
        self.assertEqual(format_currency_de(Decimal("100")), f"100,00{NBSP}€")

    def test_custom_symbol(self):
        self.assertEqual(format_currency_de(Decimal("1234.50"), "$"), f"1.234,50{NBSP}$")

    def test_matches_the_currency_template_filter(self):
        """The email and the |currency filter used by the PDF must agree."""
        from my_practice.templatetags.payment_tags import currency

        for value in (Decimal("0.99"), Decimal("1234.50"), Decimal("11064.03")):
            self.assertEqual(currency(value), format_currency_de(value))


class RenderEmailTemplateTest(TestCase):
    """Rendering is total: free text typed by the practitioner must never crash a send."""

    def test_substitutes_known_placeholders(self):
        self.assertEqual(
            render_email_template("Hallo {salutation}!", {"salutation": "Liebe:r Max"}),
            "Hallo Liebe:r Max!",
        )

    def test_unknown_placeholder_left_standing_instead_of_raising(self):
        # Previously str.format() raised KeyError and aborted the send.
        self.assertEqual(
            render_email_template("Betrag: {Betrag}", {"amount": "5"}), "Betrag: {Betrag}"
        )

    def test_stray_opening_brace_does_not_raise(self):
        # e.g. the practitioner typing a brace in ordinary prose.
        self.assertEqual(render_email_template("costs { or so", {}), "costs { or so")

    def test_unmatched_closing_brace_does_not_raise(self):
        self.assertEqual(render_email_template("50%} off", {}), "50%} off")

    def test_attribute_traversal_is_not_a_placeholder(self):
        """{obj.__class__} was reachable under str.format; now it is literal text."""
        out = render_email_template("{client.__class__}", {"client": object()})
        self.assertEqual(out, "{client.__class__}")

    def test_repeated_placeholder_substituted_everywhere(self):
        self.assertEqual(render_email_template("{a}-{a}", {"a": "x"}), "x-x")

    def test_non_string_context_values_are_coerced(self):
        self.assertEqual(render_email_template("n={n}", {"n": 3}), "n=3")


class ValidateEmailTemplatePlaceholdersTest(TestCase):
    """Save-time validation is what surfaces a typo while it can still be fixed."""

    def test_accepts_every_supported_placeholder(self):
        text = "{salutation} {sessions_intro} {invoice_number} {amount} {date} {client_name}"
        validate_email_template_placeholders(text)  # must not raise

    def test_accepts_text_without_placeholders(self):
        validate_email_template_placeholders("Plain text, no placeholders.")

    def test_rejects_unknown_placeholder(self):
        with self.assertRaises(ValidationError):
            validate_email_template_placeholders("Betrag: {Betrag}")

    def test_error_names_the_offending_placeholder(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_email_template_placeholders("{Betrag} and {Datum}")
        message = str(ctx.exception)
        self.assertIn("{Betrag}", message)
        self.assertIn("{Datum}", message)

    def test_stray_brace_is_not_treated_as_a_placeholder(self):
        validate_email_template_placeholders("a { b } c")  # must not raise

    def test_empty_value_accepted(self):
        validate_email_template_placeholders("")

    def test_enforced_by_the_admin_form(self):
        """The admin is the only edit path for these fields — check it really rejects."""
        from django.contrib import admin as django_admin
        from my_practice.models import Practice

        model_admin = django_admin.site._registry[Practice]
        form_class = model_admin.get_form(request=None)

        practice = Practice(name="Test Practice", slug="validator-admin-check")
        form = form_class(
            instance=practice,
            data={
                **{f: getattr(practice, f, "") or "" for f in form_class.base_fields},
                "name": "Test Practice",
                "slug": "validator-admin-check",
                "invoice_email_subject_de": "Rechnung {invoice_number}",
                "invoice_email_body_de": "{salutation},\n\nBetrag: {Betrag}",
            },
        )
        self.assertFalse(form.is_valid())
        self.assertIn("invoice_email_body_de", form.errors)
        self.assertIn("{Betrag}", str(form.errors["invoice_email_body_de"]))
        # ...and the correctly-spelled sibling field is not blamed
        self.assertNotIn("invoice_email_subject_de", form.errors)


class EmailContentBuilderTestBase(TestCase):
    """Shared fixtures: one practice, one German client, one English client."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="email-content-builders",
            title="Test Practitioner",
            email="practice@practice.example",
            city="Berlin",
            email_signature="Viele Grüße\nAnna Schmidt",
        )
        self.client_de = Client.objects.create(
            client_code="AB-1",
            full_name="Max Mustermann",
            email="max@example.com",
            language="de",
            practice=self.practice,
        )
        self.client_en = Client.objects.create(
            client_code="CD-2",
            full_name="Jane Doe",
            email="jane@example.com",
            language="en",
            practice=self.practice,
        )


class SalutationTest(EmailContentBuilderTestBase):
    def test_german_fallback_uses_first_name(self):
        self.assertEqual(get_salutation_for_client(self.client_de), "Liebe:r Max")

    def test_english_fallback_uses_first_name(self):
        self.assertEqual(get_salutation_for_client(self.client_en), "Dear Jane")

    def test_custom_salutation_overrides_fallback(self):
        self.client_de.salutation = "Hallo Max"
        self.assertEqual(get_salutation_for_client(self.client_de), "Hallo Max")

    def test_blank_full_name_falls_back_to_client(self):
        nameless = Client.objects.create(
            client_code="EF-3", full_name="", language="en", practice=self.practice
        )
        self.assertEqual(get_salutation_for_client(nameless), "Dear Client")


class InvoiceEmailContentTest(EmailContentBuilderTestBase):
    def _make_invoice(self, client, total="1234.50"):
        invoice = Invoice.objects.create(
            client=client,
            invoice_number=f"{client.client_code}-1",
            status="draft",
            total=Decimal(total),
            practice=self.practice,
        )
        # Invoice.save() forces invoice_date to today when creating a draft,
        # so pin it afterwards to keep the rendered date assertion stable.
        invoice.invoice_date = date(2026, 8, 15)
        invoice.save(update_fields=["invoice_date"])
        return invoice

    def test_amount_uses_german_format_matching_the_attached_pdf(self):
        """Regression: an inline f-string produced "1234.50 €" beside a PDF reading "1.234,50 €"."""
        invoice = self._make_invoice(self.client_de)
        context = prepare_invoice_email_context(invoice, self.practice)
        self.assertEqual(context["amount"], f"1.234,50{NBSP}€")
        self.assertNotIn("1234.50", context["amount"])

    def test_context_carries_every_documented_placeholder(self):
        invoice = self._make_invoice(self.client_de)
        context = prepare_invoice_email_context(invoice, self.practice)
        self.assertEqual(context["invoice_number"], "AB-1-1")
        self.assertEqual(context["date"], "15.08.2026")
        self.assertEqual(context["client_name"], "Max Mustermann")
        self.assertEqual(context["salutation"], "Liebe:r Max")

    def test_custom_salutation_overrides_context(self):
        invoice = self._make_invoice(self.client_de)
        context = prepare_invoice_email_context(invoice, self.practice, custom_salutation="Servus")
        self.assertEqual(context["salutation"], "Servus")

    def test_german_client_gets_german_template(self):
        subject, body = get_invoice_email_content(self._make_invoice(self.client_de), self.practice)
        self.assertEqual(subject, "Rechnung AB-1-1")
        self.assertIn("anbei erhalten Sie die Rechnung", body)
        self.assertIn(f"1.234,50{NBSP}€", body)

    def test_english_client_gets_english_template(self):
        subject, body = get_invoice_email_content(self._make_invoice(self.client_en), self.practice)
        self.assertEqual(subject, "Invoice CD-2-1")
        self.assertIn("Please find attached invoice", body)
        self.assertNotIn("anbei erhalten Sie", body)

    def test_amount_rendered_into_body_not_left_as_placeholder(self):
        _, body = get_invoice_email_content(self._make_invoice(self.client_de), self.practice)
        self.assertNotIn("{amount}", body)
        self.assertNotIn("{invoice_number}", body)
        self.assertNotIn("{salutation}", body)

    def test_signature_appended(self):
        _, body = get_invoice_email_content(self._make_invoice(self.client_de), self.practice)
        self.assertTrue(body.endswith("-- \nViele Grüße\nAnna Schmidt"))

    def test_no_dangling_delimiter_when_signature_empty(self):
        """An empty signature must not leave a bare "-- " sig delimiter on the mail."""
        self.practice.email_signature = ""
        _, body = get_invoice_email_content(self._make_invoice(self.client_de), self.practice)
        self.assertNotIn("-- \n", body)

    def test_custom_message_appended_before_signature(self):
        _, body = get_invoice_email_content(
            self._make_invoice(self.client_de), self.practice, custom_message="Bis bald!"
        )
        self.assertIn("Bis bald!", body)
        self.assertLess(body.index("Bis bald!"), body.index("Viele Grüße"))

    def test_broken_template_renders_instead_of_crashing_the_send(self):
        """A template already stored with a typo must not abort the send."""
        self.practice.invoice_email_body_de = "{salutation},\n\nBetrag: {Betrag}"
        _, body = get_invoice_email_content(self._make_invoice(self.client_de), self.practice)
        self.assertIn("Liebe:r Max", body)
        self.assertIn("{Betrag}", body)


class SessionsIntroTest(EmailContentBuilderTestBase):
    """The opening sentence summarising which sessions an invoice covers."""

    def _invoice_with_sessions(self, client, session_dates):
        service_type = ServiceType.objects.create(
            practice=self.practice,
            code="EINZEL",
            name="Einzelsitzung",
            name_de="Einzelsitzung",
            name_en="Individual session",
        )
        invoice = Invoice.objects.create(
            client=client,
            invoice_number=f"{client.client_code}-9",
            status="draft",
            total=Decimal("100.00"),
            practice=self.practice,
        )
        for d in session_dates:
            session = Session.objects.create(client=client, session_date=d, duration=60)
            InvoiceItem.objects.create(
                invoice=invoice,
                session=session,
                service_type=service_type,
                rate=Decimal("50.00"),
                quantity=Decimal("1"),
            )
        return invoice

    def test_single_month_german_singular(self):
        invoice = self._invoice_with_sessions(self.client_de, [date(2026, 7, 3)])
        _, body = get_invoice_email_content(invoice, self.practice)
        self.assertIn("unsere Sitzung im Juli", body)

    def test_single_month_german_plural(self):
        invoice = self._invoice_with_sessions(self.client_de, [date(2026, 7, 3), date(2026, 7, 10)])
        _, body = get_invoice_email_content(invoice, self.practice)
        self.assertIn("unsere Sitzungen im Juli", body)

    def test_single_month_english(self):
        invoice = self._invoice_with_sessions(self.client_en, [date(2026, 7, 3), date(2026, 7, 10)])
        _, body = get_invoice_email_content(invoice, self.practice)
        self.assertIn("our sessions in July", body)

    def test_spanning_months_counts_sessions(self):
        invoice = self._invoice_with_sessions(self.client_de, [date(2026, 6, 30), date(2026, 7, 1)])
        _, body = get_invoice_email_content(invoice, self.practice)
        self.assertIn("unsere letzten 2 Sitzungen", body)

    def test_no_sessions_yields_no_intro(self):
        invoice = self._invoice_with_sessions(self.client_de, [])
        _, body = get_invoice_email_content(invoice, self.practice)
        self.assertNotIn("Sitzung", body)
        self.assertNotIn("{sessions_intro}", body)


class DocumentEmailContentTest(EmailContentBuilderTestBase):
    """The five attachment-accompanying builders, each in both languages.

    Parametrised over (builder, german marker, english marker) so a newly added
    builder is a one-line addition rather than another copy of the same test.
    """

    CASES = [
        (
            get_questionnaire_email_content,
            "Anamnesebogen",
            "Questionnaire",
            "anbei auch der Anamnesebogen",
            "Here is also the questionnaire",
        ),
        (
            get_intake_email_content,
            "Aufnahmebogen",
            "Intake Form",
            "anbei findest du den Aufnahmebogen",
            "please find attached the intake form",
        ),
        (
            get_gdpr_deletion_email_content,
            "Löschung Ihrer gespeicherten Daten",
            "Deletion of your personal data",
            "Art. 17 DSGVO",
            "Art. 17 GDPR",
        ),
        (
            get_questionnaire_pdf_email_content,
            "Fragebogen",
            "Questionnaire",
            "anbei findest du einen kurzen Fragebogen",
            "please find attached a short questionnaire",
        ),
        (
            get_contract_email_content,
            "Behandlungsvertrag",
            "Treatment Contract",
            "anbei findest du den Behandlungsvertrag",
            "please find attached the therapy agreement",
        ),
    ]

    def test_german_subject_and_body(self):
        for builder, subject_de, _subject_en, body_de, _body_en in self.CASES:
            with self.subTest(builder=builder.__name__):
                subject, body = builder(self.client_de, self.practice)
                self.assertEqual(subject, subject_de)
                self.assertIn(body_de, body)
                self.assertTrue(body.startswith("Liebe:r Max,"))

    def test_english_subject_and_body(self):
        for builder, _subject_de, subject_en, _body_de, body_en in self.CASES:
            with self.subTest(builder=builder.__name__):
                subject, body = builder(self.client_en, self.practice)
                self.assertEqual(subject, subject_en)
                self.assertIn(body_en, body)
                self.assertTrue(body.startswith("Dear Jane,"))

    def test_languages_produce_different_bodies(self):
        """Guards against a builder ignoring client.language entirely."""
        for builder, *_ in self.CASES:
            with self.subTest(builder=builder.__name__):
                _, body_de = builder(self.client_de, self.practice)
                _, body_en = builder(self.client_en, self.practice)
                self.assertNotEqual(body_de, body_en)

    def test_signature_appended_when_set(self):
        for builder, *_ in self.CASES:
            with self.subTest(builder=builder.__name__):
                _, body = builder(self.client_de, self.practice)
                self.assertTrue(body.endswith("-- \nViele Grüße\nAnna Schmidt"))

    def test_no_dangling_delimiter_when_signature_empty(self):
        self.practice.email_signature = ""
        for builder, *_ in self.CASES:
            with self.subTest(builder=builder.__name__):
                _, body = builder(self.client_de, self.practice)
                self.assertNotIn("-- \n", body)


class TimeOffNoticeContentTest(EmailContentBuilderTestBase):
    """Unlike the others this returns all four strings at once, for an editable form."""

    def _timeoff(self, start, end):
        return TimeOff.objects.create(start_date=start, end_date=end, title="Sommerurlaub")

    def test_single_period_same_month(self):
        periods = [self._timeoff(date(2026, 7, 24), date(2026, 7, 28))]
        subject_de, body_de, subject_en, body_en = get_timeoff_notice_default_content(
            periods, self.practice
        )
        self.assertEqual(subject_de, "Praxis geschlossen: 24.-28. Juli")
        self.assertEqual(subject_en, "Practice closed: 24-28th July")
        self.assertIn("Fr 24. - Di 28. Juli", body_de)
        self.assertIn("Fri 24th - Tue 28th July", body_en)

    def test_single_period_spanning_months(self):
        periods = [self._timeoff(date(2026, 6, 30), date(2026, 7, 2))]
        subject_de, _, subject_en, _ = get_timeoff_notice_default_content(periods, self.practice)
        self.assertEqual(subject_de, "Praxis geschlossen: 30. Juni-2. Juli")
        self.assertEqual(subject_en, "Practice closed: 30th June-2nd July")

    def test_multiple_periods_rendered_as_bullets(self):
        periods = [
            self._timeoff(date(2026, 7, 24), date(2026, 7, 28)),
            self._timeoff(date(2026, 8, 10), date(2026, 8, 14)),
        ]
        subject_de, body_de, _, body_en = get_timeoff_notice_default_content(periods, self.practice)
        self.assertIn("24.-28. Juli", subject_de)
        self.assertIn("10.-14. August", subject_de)
        self.assertIn("- Fr 24. - Di 28. Juli", body_de)
        self.assertIn("- Mo 10. - Fr 14. August", body_de)
        self.assertIn("- Fri 24th - Tue 28th July", body_en)

    def test_salutation_left_as_placeholder_for_per_recipient_render(self):
        """The body is filled in per recipient at send time, so it must stay a placeholder."""
        periods = [self._timeoff(date(2026, 7, 24), date(2026, 7, 28))]
        _, body_de, _, body_en = get_timeoff_notice_default_content(periods, self.practice)
        self.assertTrue(body_de.startswith("{salutation},"))
        self.assertTrue(body_en.startswith("{salutation},"))
        # and that placeholder must survive a real render round-trip
        rendered = render_email_template(body_de, {"salutation": "Liebe:r Max"})
        self.assertTrue(rendered.startswith("Liebe:r Max,"))

    def test_english_ordinal_suffixes(self):
        cases = {
            1: "1st",
            2: "2nd",
            3: "3rd",
            4: "4th",
            11: "11th",
            12: "12th",
            13: "13th",
            21: "21st",
        }
        for day, expected in cases.items():
            with self.subTest(day=day):
                periods = [self._timeoff(date(2026, 7, day), date(2026, 7, day))]
                _, _, subject_en, _ = get_timeoff_notice_default_content(periods, self.practice)
                self.assertIn(expected, subject_en)
