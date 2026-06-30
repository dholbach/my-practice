"""Tests for GebüH billing — Phase 1 models and Phase 2 quick-entry UI."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import Client, Practice, Session, UserPractice
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
            reverse("client_detail", kwargs={"pk": self.client_obj.pk}) + "#tab-sitzungen",
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
            reverse("client_detail", kwargs={"pk": regular.pk}) + "#tab-sitzungen",
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
        self.assertTrue(any("Alleinleistung" in t for t in warning_texts))
