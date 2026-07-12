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
        self.assertEqual(b["vereinbarter_betrag"], Decimal("90.00"))  # falls back to item.rate

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
