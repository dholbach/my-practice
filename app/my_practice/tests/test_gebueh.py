"""Tests for GebüH billing — Phase 1 models, Phase 2 quick-entry UI, Phase 3 PDF blocks."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import Client, Invoice, InvoiceItem, Practice, ServiceType, Session, UserPractice
from ..models.gebueh import GebuhZiffer, Leistungserfassung


def _make_practice(slug="gebueh-test"):
    return Practice.objects.create(
        name="Test Practice",
        slug=slug,
        title="Heilpraktikerin für Psychotherapie",
        email="test@example.com",
        city="Berlin",
    )


def _make_client(practice, code="TS", needs_gebueh=True):
    return Client.objects.create(
        client_code=code,
        full_name="Test Mustermann",
        practice=practice,
        hourly_rate_60=Decimal("90.00"),
        needs_gebueh_invoice=needs_gebueh,
    )


def _make_ziffer(nummer="19.2", satz_max="46.00", sort_order=10):
    obj, _ = GebuhZiffer.objects.get_or_create(
        nummer=nummer,
        defaults={
            "bezeichnung": "Psychotherapie 50–90 Min",
            "satz_max": Decimal(satz_max),
            "satz_min": Decimal("26.00"),
            "sort_order": sort_order,
        },
    )
    return obj


class GebuhZifferModelTest(TestCase):
    def test_str(self):
        z = _make_ziffer()
        self.assertEqual(str(z), "Ziffer 19.2 – Psychotherapie 50–90 Min")

    def test_ordering(self):
        # Seeded Ziffern: sort_order 10=Ziffer 1, 20=19.5, 30=19.1, 40=19.2
        nums = list(GebuhZiffer.objects.values_list("nummer", flat=True))
        self.assertLess(nums.index("1"), nums.index("19.2"))


class LeistungserfassungModelTest(TestCase):
    def setUp(self):
        self.practice = _make_practice()
        self.client_obj = _make_client(self.practice)
        self.session = Session.objects.create(
            client=self.client_obj,
            session_date=date.today(),
            duration=60,
        )
        self.ziffer = _make_ziffer()

    def test_compute_vereinbarter_betrag(self):
        # 90 € / h × 60 min = 90.00 €
        result = Leistungserfassung.compute_vereinbarter_betrag(self.session)
        self.assertEqual(result, Decimal("90.00"))

    def test_compute_vereinbarter_betrag_partial(self):
        # 90 € / h × 45 min = 67.50 €
        self.session.duration = 45
        self.session.save()
        result = Leistungserfassung.compute_vereinbarter_betrag(self.session)
        self.assertEqual(result, Decimal("67.50"))

    def test_str(self):
        le = Leistungserfassung.objects.create(
            session=self.session,
            ziffer=self.ziffer,
            betrag=self.ziffer.satz_max,
            vereinbarter_betrag=Decimal("90.00"),
        )
        self.assertIn("19.2", str(le))


class GebuhLeistungViewTest(TestCase):
    def setUp(self):
        self.practice = _make_practice(slug="gebueh-view-test")
        self.user = User.objects.create_user(username="doc", password="secret")
        UserPractice.objects.create(user=self.user, practice=self.practice)
        self.http = TestClient()
        self.http.login(username="doc", password="secret")
        session_cookie = self.http.session
        session_cookie["current_practice_id"] = self.practice.pk
        session_cookie.save()

        self.client_obj = _make_client(self.practice)
        self.session = Session.objects.create(
            client=self.client_obj,
            session_date=date.today(),
            duration=60,
        )
        self.ziffer = _make_ziffer()

    def _url(self):
        return reverse(
            "gebueh_leistung_create",
            kwargs={"client_pk": self.client_obj.pk, "session_pk": self.session.pk},
        )

    def test_get_shows_form(self):
        resp = self.http.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "19.2")

    def test_post_creates_entries(self):
        resp = self.http.post(self._url(), {"ziffern": [self.ziffer.pk]})
        self.assertRedirects(
            resp,
            reverse("client_detail", kwargs={"pk": self.client_obj.pk}) + "#ptab-protokoll",
        )
        self.assertEqual(Leistungserfassung.objects.filter(session=self.session).count(), 1)
        le = Leistungserfassung.objects.get(session=self.session)
        self.assertEqual(le.betrag, self.ziffer.satz_max)
        self.assertEqual(le.vereinbarter_betrag, Decimal("90.00"))

    def test_post_caps_betrag_at_actual_session_fee(self):
        """
        satz_max is only the fee schedule's ceiling for a code — a short
        session's actual (prorated) fee can be lower, and betrag should never
        exceed what's actually charged, even if the code allows more.
        """
        short_session = Session.objects.create(
            client=self.client_obj, session_date=date.today(), duration=15
        )
        # client hourly_rate_60=90.00 → 15-min session fee prorates to 22.50,
        # below self.ziffer.satz_max (46.00).
        url = reverse(
            "gebueh_leistung_create",
            kwargs={"client_pk": self.client_obj.pk, "session_pk": short_session.pk},
        )
        self.http.post(url, {"ziffern": [self.ziffer.pk]})
        le = Leistungserfassung.objects.get(session=short_session)
        self.assertEqual(le.betrag, Decimal("22.50"))

    def test_post_replaces_existing_entries(self):
        ziffer2, _ = GebuhZiffer.objects.get_or_create(
            nummer="19.5",
            defaults={
                "bezeichnung": "Exploration",
                "satz_max": Decimal("46.00"),
                "satz_min": Decimal("15.50"),
                "sort_order": 20,
            },
        )
        Leistungserfassung.objects.create(
            session=self.session,
            ziffer=self.ziffer,
            betrag=self.ziffer.satz_max,
            vereinbarter_betrag=Decimal("90.00"),
        )
        self.http.post(self._url(), {"ziffern": [ziffer2.pk]})
        ziffern_recorded = list(
            Leistungserfassung.objects.filter(session=self.session).values_list(
                "ziffer__nummer", flat=True
            )
        )
        self.assertEqual(ziffern_recorded, ["19.5"])

    def test_post_empty_clears_entries(self):
        Leistungserfassung.objects.create(
            session=self.session,
            ziffer=self.ziffer,
            betrag=self.ziffer.satz_max,
            vereinbarter_betrag=Decimal("90.00"),
        )
        self.http.post(self._url(), {})
        self.assertEqual(Leistungserfassung.objects.filter(session=self.session).count(), 0)

    def test_non_gebueh_client_redirects(self):
        regular = _make_client(self.practice, code="RG", needs_gebueh=False)
        session2 = Session.objects.create(client=regular, session_date=date.today(), duration=60)
        url = reverse(
            "gebueh_leistung_create",
            kwargs={"client_pk": regular.pk, "session_pk": session2.pk},
        )
        resp = self.http.get(url)
        self.assertRedirects(
            resp,
            reverse("client_detail", kwargs={"pk": regular.pk}) + "#ptab-protokoll",
        )

    def test_frequency_warning(self):
        ziffer_freq, _ = GebuhZiffer.objects.get_or_create(
            nummer="1",
            defaults={
                "bezeichnung": "Anamnese",
                "satz_max": Decimal("41.00"),
                "satz_min": Decimal("15.40"),
                "max_haeufigkeit": 3,
                "bezugszeitraum_tage": 180,
                "sort_order": 5,
            },
        )
        # Pre-fill 3 existing entries within 180 days
        for i in range(3):
            past_session = Session.objects.create(
                client=self.client_obj,
                session_date=date.today() - timedelta(days=i + 1),
                duration=60,
            )
            Leistungserfassung.objects.create(
                session=past_session,
                ziffer=ziffer_freq,
                betrag=ziffer_freq.satz_max,
                vereinbarter_betrag=Decimal("90.00"),
            )
        resp = self.http.post(self._url(), {"ziffern": [ziffer_freq.pk]}, follow=True)
        messages = list(resp.context["messages"])
        warning_texts = [str(m) for m in messages if m.level_tag == "warning"]
        self.assertTrue(any("Ziffer 1" in t for t in warning_texts))

    def test_alleinleistung_warning(self):
        ziffer4, _ = GebuhZiffer.objects.get_or_create(
            nummer="4",
            defaults={
                "bezeichnung": "Eingehende Beratung",
                "satz_max": Decimal("22.00"),
                "satz_min": Decimal("16.40"),
                "sort_order": 90,
            },
        )
        resp = self.http.post(self._url(), {"ziffern": [self.ziffer.pk, ziffer4.pk]}, follow=True)
        messages_list = list(resp.context["messages"])
        warning_texts = [str(m) for m in messages_list if m.level_tag == "warning"]
        self.assertTrue(any("Alleinleistung" in t or "standalone" in t for t in warning_texts))


class GebuhPdfBlocksTest(TestCase):
    """Tests for _build_gebueh_blocks — the PDF context helper."""

    def setUp(self):
        from ..utils.gebueh_helpers import build_gebueh_blocks, get_arbeitsdiagnose

        self._build = build_gebueh_blocks
        self._diagnose = get_arbeitsdiagnose

        self.practice = _make_practice(slug="gebueh-pdf-test")
        self.client_obj = _make_client(self.practice, code="PDF")
        self.session = Session.objects.create(
            client=self.client_obj, session_date=date.today(), duration=60
        )
        self.ziffer, _ = GebuhZiffer.objects.get_or_create(
            nummer="19.2",
            defaults={
                "bezeichnung": "Psychotherapie 50–90 Min",
                "satz_max": Decimal("46.00"),
                "satz_min": Decimal("26.00"),
                "sort_order": 40,
            },
        )
        self.service_type = ServiceType.objects.first() or ServiceType.objects.create(
            name="Therapie", name_de="Therapiesitzung", name_en="Therapy session"
        )
        self.invoice = Invoice.objects.create(
            client=self.client_obj,
            practice=self.practice,
            invoice_number="INV-001",
            status="draft",
        )
        self.item = InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=self.session,
            rate=Decimal("90.00"),
            quantity=Decimal("1"),
            total=Decimal("90.00"),
        )

    def _record_leistung(self, ziffer=None):
        z = ziffer or self.ziffer
        return Leistungserfassung.objects.create(
            session=self.session,
            ziffer=z,
            betrag=z.satz_max,
            vereinbarter_betrag=Decimal("90.00"),
        )

    def test_block_with_leistung(self):
        self._record_leistung()
        blocks = self._build(self.invoice)
        self.assertEqual(len(blocks), 1)
        b = blocks[0]
        self.assertEqual(len(b["leistungen"]), 1)
        self.assertEqual(b["gebueh_sum"], Decimal("46.00"))
        self.assertEqual(b["vereinbarter_betrag"], Decimal("90.00"))
        self.assertEqual(b["restbetrag"], Decimal("44.00"))

    def test_block_without_leistung(self):
        blocks = self._build(self.invoice)
        b = blocks[0]
        self.assertEqual(b["leistungen"], [])
        self.assertEqual(b["gebueh_sum"], Decimal("0"))
        self.assertEqual(b["vereinbarter_betrag"], Decimal("90.00"))  # item.total, no leistungen

    def test_restbetrag_clamped_to_zero(self):
        # Two expensive Ziffern whose sum exceeds vereinbarter_betrag
        z2, _ = GebuhZiffer.objects.get_or_create(
            nummer="19.5",
            defaults={
                "bezeichnung": "Exploration",
                "satz_max": Decimal("46.00"),
                "satz_min": Decimal("15.50"),
                "sort_order": 20,
            },
        )
        self._record_leistung(self.ziffer)  # 46 €
        self._record_leistung(z2)  # 46 € → total 92 € > 90 €
        blocks = self._build(self.invoice)
        self.assertEqual(blocks[0]["restbetrag"], Decimal("0"))

    def test_gebueh_total_for_blocks_sums_across_sessions(self):
        from ..utils.gebueh_helpers import gebueh_total_for_blocks

        session2 = Session.objects.create(
            client=self.client_obj, session_date=date.today(), duration=60
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=session2,
            rate=Decimal("90.00"),
            quantity=Decimal("1"),
            total=Decimal("90.00"),
        )
        self._record_leistung()  # 46.00 on self.session
        Leistungserfassung.objects.create(
            session=session2,
            ziffer=self.ziffer,
            betrag=self.ziffer.satz_max,
            vereinbarter_betrag=Decimal("90.00"),
        )  # another 46.00 on session2

        blocks = self._build(self.invoice)
        self.assertEqual(gebueh_total_for_blocks(blocks), Decimal("92.00"))

    def test_gebueh_total_for_blocks_zero_when_no_leistungen(self):
        from ..utils.gebueh_helpers import gebueh_total_for_blocks

        blocks = self._build(self.invoice)
        self.assertEqual(gebueh_total_for_blocks(blocks), Decimal("0"))

    def test_get_arbeitsdiagnose_no_profile(self):
        # No ClientProfile exists yet — should return empty string, not raise
        result = self._diagnose(self.client_obj)
        self.assertEqual(result, "")

    def test_get_arbeitsdiagnose_with_profile(self):
        from ..models import ClientProfile

        # arbeitsdiagnose is Fernet-encrypted; just verify no exception is raised
        # and the result is a string (decrypted value or empty if no key in test env)
        ClientProfile.objects.create(client=self.client_obj, arbeitsdiagnose="F32.1")
        result = self._diagnose(self.client_obj)
        self.assertIsInstance(result, str)


class GebuhPdfTemplateTest(TestCase):
    """
    Tests the invoice_pdf_de.html GebüH block markup directly via render_to_string,
    without going through WeasyPrint — faster and lets us assert on the rendered HTML.
    """

    def setUp(self):
        from ..utils.gebueh_helpers import build_gebueh_blocks, gebueh_total_for_blocks

        self.practice = _make_practice(slug="gebueh-pdf-template-test")
        self.client_obj = _make_client(self.practice, code="TPL")
        self.session = Session.objects.create(
            client=self.client_obj, session_date=date.today(), duration=60
        )
        self.service_type = ServiceType.objects.create(
            name="Therapie", name_de="Therapiesitzung", name_en="Therapy session"
        )
        self.invoice = Invoice.objects.create(
            client=self.client_obj, practice=self.practice, invoice_number="TPL-1", status="draft"
        )
        self.item = InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=self.session,
            rate=Decimal("90.00"),
            quantity=Decimal("1"),
            total=Decimal("90.00"),
        )
        self._build = build_gebueh_blocks
        self._total = gebueh_total_for_blocks

    def _render(self):
        """Render and return only the <body> — the <style> block contains the
        same class names as selectors, which would false-trigger substring
        assertions if included."""
        from django.template.loader import render_to_string

        blocks = self._build(self.invoice)
        html = render_to_string(
            "my_practice/invoice_pdf_de.html",
            {
                "invoice": self.invoice,
                "practice": self.practice,
                "gebueh_blocks": blocks,
                "gebueh_total": self._total(blocks),
                "arbeitsdiagnose": "",
            },
        )
        return html.split("<body>", 1)[1]

    def test_headline_row_shows_service_and_amount(self):
        html = self._render()
        self.assertIn("gebueh-headline", html)
        self.assertIn("Therapiesitzung", html)
        self.assertIn("90,00", html)

    def test_no_leistungen_gets_solo_headline_with_border(self):
        html = self._render()
        self.assertIn("gebueh-headline-solo", html)
        self.assertNotIn("gebueh-detail-row", html)

    def test_single_code_shown_in_detail_line(self):
        z, _ = GebuhZiffer.objects.get_or_create(
            nummer="19.2",
            defaults={
                "bezeichnung": "Psychotherapie 50–90 Min",
                "satz_max": Decimal("46.00"),
                "satz_min": Decimal("26.00"),
                "sort_order": 40,
            },
        )
        Leistungserfassung.objects.create(
            session=self.session, ziffer=z, betrag=z.satz_max, vereinbarter_betrag=Decimal("90.00")
        )
        html = self._render()
        self.assertIn("gebueh-detail-row", html)
        self.assertNotIn("gebueh-headline-solo", html)
        self.assertIn("Ziffer 19.2", html)
        self.assertIn("Psychotherapie 50–90 Min", html)

    def test_multiple_codes_all_shown_in_one_detail_line(self):
        z1, _ = GebuhZiffer.objects.get_or_create(
            nummer="19.2",
            defaults={
                "bezeichnung": "Psychotherapie 50–90 Min",
                "satz_max": Decimal("46.00"),
                "satz_min": Decimal("26.00"),
                "sort_order": 40,
            },
        )
        z2, _ = GebuhZiffer.objects.get_or_create(
            nummer="4",
            defaults={
                "bezeichnung": "Eingehende Beratung",
                "satz_max": Decimal("22.00"),
                "satz_min": Decimal("16.40"),
                "sort_order": 90,
            },
        )
        for z in (z1, z2):
            Leistungserfassung.objects.create(
                session=self.session,
                ziffer=z,
                betrag=z.satz_max,
                vereinbarter_betrag=Decimal("90.00"),
            )
        html = self._render()
        self.assertIn("Ziffer 19.2", html)
        self.assertIn("Ziffer 4", html)
        # Both codes collapse into a single detail row, not one row per code.
        self.assertEqual(html.count('class="gebueh-detail-row"'), 1)

    def test_gebueh_gesamt_total_shown_when_leistungen_recorded(self):
        z, _ = GebuhZiffer.objects.get_or_create(
            nummer="19.2",
            defaults={
                "bezeichnung": "Psychotherapie 50–90 Min",
                "satz_max": Decimal("46.00"),
                "satz_min": Decimal("26.00"),
                "sort_order": 40,
            },
        )
        Leistungserfassung.objects.create(
            session=self.session, ziffer=z, betrag=z.satz_max, vereinbarter_betrag=Decimal("90.00")
        )
        html = self._render()
        self.assertIn("GebüH gesamt", html)

    def test_gebueh_gesamt_total_hidden_when_no_leistungen(self):
        html = self._render()
        self.assertNotIn("GebüH gesamt", html)


class GebuhInvoiceDetailViewTest(TestCase):
    """Tests the tightened GebüH block on the web invoice_detail.html view:
    one headline row per visit + a single collapsed detail line (codes +
    Restbetrag), mirroring the invoice PDF layout — not a row per code plus
    separate subtotal/remaining rows."""

    def setUp(self):
        self.practice = _make_practice(slug="gebueh-invoice-detail-test")
        self.client_obj = _make_client(self.practice, code="TID")
        self.session = Session.objects.create(
            client=self.client_obj, session_date=date.today(), duration=60
        )
        self.service_type = ServiceType.objects.create(
            name="Therapie", name_de="Therapiesitzung", name_en="Therapy session"
        )
        self.invoice = Invoice.objects.create(
            client=self.client_obj, practice=self.practice, invoice_number="TID-1", status="draft"
        )
        self.item = InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=self.session,
            rate=Decimal("90.00"),
            quantity=Decimal("1"),
            total=Decimal("90.00"),
        )

        self.user = User.objects.create_user(username="testuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.test_client = TestClient()
        self.test_client.login(username="testuser", password="testpass123")

    def _get(self):
        response = self.test_client.get(reverse("invoice_detail", kwargs={"pk": self.invoice.pk}))
        return response.content.decode()

    def test_no_leistungen_shows_headline_row_only(self):
        html = self._get()
        self.assertIn("Therapiesitzung", html)
        self.assertNotIn("Code 19.2", html)
        # No recorded GebüH codes → gebueh_total is 0 → totals-block row hidden.
        self.assertNotIn("GebüH gesamt", html)

    def test_recorded_codes_collapse_into_one_detail_line(self):
        z1 = _make_ziffer(nummer="19.2", satz_max="46.00", sort_order=40)
        z2 = _make_ziffer(nummer="4", satz_max="18.50", sort_order=10)
        for z in (z1, z2):
            Leistungserfassung.objects.create(
                session=self.session,
                ziffer=z,
                betrag=z.satz_max,
                vereinbarter_betrag=Decimal("90.00"),
            )
        html = self._get()
        self.assertIn("Code 19.2", html)
        self.assertIn("Code 4", html)
        self.assertIn("Restbetrag", html)
        # Both codes + the Restbetrag are one collapsed line, not separate rows.
        self.assertEqual(html.count("Code "), 2)
        self.assertNotIn("GebüH subtotal", html)
        self.assertNotIn("GebüH-Zwischensumme", html)

    def test_totals_block_shows_gebueh_total_alongside_grand_total(self):
        from ..templatetags.payment_tags import currency

        z1 = _make_ziffer(nummer="19.2", satz_max="46.00", sort_order=40)
        z2 = _make_ziffer(nummer="4", satz_max="18.50", sort_order=10)
        total = Decimal("0")
        for z in (z1, z2):
            Leistungserfassung.objects.create(
                session=self.session,
                ziffer=z,
                betrag=z.satz_max,
                vereinbarter_betrag=Decimal("90.00"),
            )
            total += z.satz_max
        html = self._get()
        self.assertIn("GebüH gesamt", html)
        self.assertIn(currency(total), html)
        self.assertIn(currency(Decimal("90.00")), html)  # invoice.total unaffected
