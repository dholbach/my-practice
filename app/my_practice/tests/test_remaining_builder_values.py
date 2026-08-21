"""
Value-level tests for the three remaining context builders.

Completes the sweep started for TaxYearContextBuilder / DashboardContextAssembler:
AnalyticsDashboardBuilder, ClientDetailContextBuilder and
FinancialListContextBuilder had no unit tests either, between them carrying 8
historical `fix:` commits.

AnalyticsDashboardBuilder mostly delegates to the analyzers in analytics_utils
(already covered by test_analytics_*.py), so what's asserted here is the
builder's *own* logic: period parsing, the earliest-data-year probe, and the
two pure reshaping functions over capacity trends.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from my_practice.models import (
    Client,
    CompanyExpense,
    CompanyWithdrawal,
    Invoice,
    InvoiceItem,
    Practice,
    ServiceType,
    Session,
    TimeOff,
    UserPractice,
)
from my_practice.utils.analytics_dashboard_builder import AnalyticsDashboardBuilder
from my_practice.utils.client_detail_builder import ClientDetailContextBuilder
from my_practice.utils.financial_list_context_builder import FinancialListContextBuilder

User = get_user_model()

YEAR = 2026


class BuilderTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rb-user", password="testpass123")
        self.practice = Practice.objects.create(name="Main", slug="rb-main", city="Berlin")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_a = Client.objects.create(
            client_code="AB-1", full_name="Max Mustermann", practice=self.practice
        )

    def make_request(self, practice=None):
        request = RequestFactory().get("/")
        request.user = self.user
        request.current_practice = practice if practice is not None else self.practice
        return request

    def make_invoice(self, *, status="sent", total="100.00", invoice_date=None, client=None):
        invoice = Invoice.objects.create(
            client=client or self.client_a,
            invoice_number=f"INV-{Invoice.objects.count() + 1:03d}",
            status=status,
            total=Decimal(total),
            practice=self.practice,
        )
        if invoice_date:
            invoice.invoice_date = invoice_date
            invoice.save(update_fields=["invoice_date"])
        return invoice


# ── ClientDetailContextBuilder ────────────────────────────────────────────────


class ClientDetailStatsTest(BuilderTestBase):
    def setUp(self):
        super().setUp()
        self.practice.allows_free_form_items = True
        self.practice.save(update_fields=["allows_free_form_items"])
        self.service_type = ServiceType.objects.create(
            practice=self.practice, code="EINZEL", name="E", name_de="E", name_en="E"
        )
        self.cancel_type = ServiceType.objects.create(
            practice=self.practice, code="CANCEL", name="A", name_de="A", name_en="A"
        )
        self.invoice = self.make_invoice(invoice_date=date(YEAR, 3, 10))

    def add_session_item(self, *, day, duration=60, cancelled=False, rate="50.00"):
        # Session.cancelled is not set directly: a P-035 signal derives it from
        # whether any of the session's invoice items uses a "cancel" service
        # type, so setting the flag by hand is silently overwritten on save.
        session = Session.objects.create(
            client=self.client_a, session_date=date(YEAR, 3, day), duration=duration
        )
        return InvoiceItem.objects.create(
            invoice=self.invoice,
            session=session,
            service_type=self.cancel_type if cancelled else self.service_type,
            rate=Decimal(rate),
            quantity=Decimal("1"),
        )

    def add_free_form_item(self, *, description="Consulting day rate", rate="500.00"):
        return InvoiceItem.objects.create(
            invoice=self.invoice,
            description=description,
            service_type=self.service_type,
            rate=Decimal(rate),
            quantity=Decimal("1"),
        )

    def build_stats(self):
        client = Client.objects.get(pk=self.client_a.pk)
        return ClientDetailContextBuilder(client, self.make_request()).build()["stats"]

    def test_session_count_and_average_duration(self):
        self.add_session_item(day=2, duration=60)
        self.add_session_item(day=9, duration=90)

        stats = self.build_stats()

        self.assertEqual(stats["session_count"], 2)
        self.assertEqual(stats["avg_duration"], 75)
        self.assertEqual(stats["total_hours"], 2.5)

    def test_free_form_items_are_excluded_from_session_stats(self):
        """Regression: they have no session and no duration, so counting them
        inflated session_count and dragged avg_duration toward zero — the card
        read "2 sessions, Ø 30 min" beside a total_hours of 1.0."""
        self.add_session_item(day=2, duration=60)
        self.add_free_form_item()

        stats = self.build_stats()

        self.assertEqual(stats["session_count"], 1)
        self.assertEqual(stats["avg_duration"], 60)
        self.assertEqual(stats["total_hours"], 1.0)

    def test_session_count_agrees_with_total_hours_for_uniform_sessions(self):
        """The two numbers sit on the same card, so they must not disagree."""
        for day in (2, 9, 16):
            self.add_session_item(day=day, duration=60)
        self.add_free_form_item()

        stats = self.build_stats()

        self.assertEqual(stats["session_count"], 3)
        self.assertEqual(stats["total_hours"], 3.0)

    def test_cancelled_sessions_excluded_from_count_and_average(self):
        self.add_session_item(day=2, duration=60)
        self.add_session_item(day=9, duration=120, cancelled=True)

        stats = self.build_stats()

        self.assertEqual(stats["session_count"], 1)
        self.assertEqual(stats["avg_duration"], 60)

    def test_avg_duration_is_zero_rather_than_dividing_by_zero(self):
        self.add_free_form_item()

        stats = self.build_stats()

        self.assertEqual(stats["session_count"], 0)
        self.assertEqual(stats["avg_duration"], 0)

    def test_first_and_last_session_dates_span_all_items(self):
        self.add_session_item(day=16)
        self.add_session_item(day=2)
        self.add_session_item(day=9)

        stats = self.build_stats()

        self.assertEqual(stats["first_session_date"], date(YEAR, 3, 2))
        self.assertEqual(stats["last_session_date"], date(YEAR, 3, 16))

    def test_open_amount_sums_only_sent_invoices(self):
        self.invoice.status = "sent"
        self.invoice.save(update_fields=["status"])
        paid = self.make_invoice(status="paid", total="900.00", invoice_date=date(YEAR, 2, 1))
        paid.save()

        stats = self.build_stats()

        self.assertEqual(stats["open_amount"], Decimal("100.00"))

    def test_last_invoice_date_ignores_drafts_and_takes_the_newest(self):
        self.make_invoice(status="sent", invoice_date=date(YEAR, 1, 5))
        self.make_invoice(status="draft")  # draft dates are forced to today

        stats = self.build_stats()

        # Invoice.Meta.ordering is -invoice_date, so the newest finalized wins.
        self.assertEqual(stats["last_invoice_date"], date(YEAR, 3, 10))

    def test_no_sessions_yields_none_dates_and_no_activity_period(self):
        stats = self.build_stats()

        self.assertIsNone(stats["first_session_date"])
        self.assertIsNone(stats["last_session_date"])
        self.assertIsNone(stats["activity_period"])


class ClientDetailActivityPeriodTest(BuilderTestBase):
    """_format_activity_period is a pure function — test it directly."""

    def fmt(self, first, last, recent):
        return ClientDetailContextBuilder._format_activity_period(first, last, recent)

    @staticmethod
    def month_label(d):
        """MONTH_ABBREVIATIONS is translated, so build the expectation from it
        rather than hardcoding "Mrz" — otherwise the test only passes where
        compiled .mo files happen to be present."""
        from my_practice.utils.chart_helpers import MONTH_ABBREVIATIONS

        return f"{MONTH_ABBREVIATIONS[d.month - 1]} {d.strftime('%y')}"

    def test_none_when_there_is_no_first_session(self):
        self.assertIsNone(self.fmt(None, None, False))

    def test_recently_active_reads_as_open_ended(self):
        start = date(YEAR, 3, 1)
        result = self.fmt(start, date(YEAR, 6, 1), True)
        self.assertIn(self.month_label(start), result)
        self.assertNotIn("–", result)

    def test_inactive_client_gets_a_closed_range(self):
        first, last = date(2024, 3, 1), date(2025, 6, 1)
        result = self.fmt(first, last, False)
        self.assertEqual(result, f"{self.month_label(first)} – {self.month_label(last)}")

    def test_single_month_is_not_rendered_as_a_range(self):
        first = date(2024, 3, 1)
        result = self.fmt(first, date(2024, 3, 20), False)
        self.assertEqual(result, self.month_label(first))


class ClientDetailBillingTest(BuilderTestBase):
    def build_context(self):
        client = Client.objects.get(pk=self.client_a.pk)
        return ClientDetailContextBuilder(client, self.make_request()).build()

    def test_no_reminder_urgency_without_sent_invoices(self):
        self.make_invoice(status="draft")

        self.assertIsNone(self.build_context()["reminder_urgency"])

    def test_reminder_urgency_escalates_with_age(self):
        today = date.today()
        cases = {
            "low": today,
            "medium": today - timedelta(days=self.practice.payment_terms_days + 1),
            "high": today - timedelta(days=self.practice.overdue_after_days + 1),
        }
        for expected, invoice_date in cases.items():
            with self.subTest(expected=expected):
                Invoice.objects.filter(client=self.client_a).delete()
                self.make_invoice(status="sent", invoice_date=invoice_date)
                self.assertEqual(self.build_context()["reminder_urgency"], expected)

    def test_current_month_str_is_zero_padded(self):
        context = self.build_context()

        year, month = context["current_month_str"].split("-")
        self.assertEqual(len(month), 2)
        self.assertEqual(int(year), date.today().year)


# ── FinancialListContextBuilder ───────────────────────────────────────────────


class FinancialListContextBuilderTest(BuilderTestBase):
    def make_expense(self, *, amount, expense_date, category="other", deductible=True):
        return CompanyExpense.objects.create(
            practice=self.practice,
            amount=Decimal(amount),
            date=expense_date,
            category=category,
            description="Test expense",
            is_tax_deductible=deductible,
        )

    def build(self, year_filter=None, **kwargs):
        builder = FinancialListContextBuilder(
            CompanyExpense.objects.filter(practice=self.practice), year_filter=year_filter
        )
        return builder.build_context(**kwargs)

    def test_grand_total_spans_all_years_even_when_filtered(self):
        self.make_expense(amount="100.00", expense_date=date(YEAR, 5, 1))
        self.make_expense(amount="50.00", expense_date=date(YEAR - 1, 5, 1))

        context, _items = self.build(year_filter=YEAR)

        self.assertEqual(context["grand_total"], Decimal("150.00"))
        self.assertEqual(context["filtered_total"], Decimal("100.00"))
        self.assertEqual(context["selected_year"], YEAR)

    def test_unfiltered_context_omits_the_filtered_keys(self):
        self.make_expense(amount="100.00", expense_date=date(YEAR, 5, 1))

        context, _items = self.build()

        self.assertNotIn("filtered_total", context)
        self.assertNotIn("selected_year", context)

    def test_items_are_year_filtered_and_newest_first(self):
        older = self.make_expense(amount="10.00", expense_date=date(YEAR, 1, 5))
        newer = self.make_expense(amount="20.00", expense_date=date(YEAR, 9, 5))
        self.make_expense(amount="99.00", expense_date=date(YEAR - 1, 9, 5))

        _context, items = self.build(year_filter=YEAR)

        self.assertEqual([i.pk for i in items], [newer.pk, older.pk])

    def test_limit_caps_the_item_list_but_not_the_totals(self):
        for month in range(1, 6):
            self.make_expense(amount="10.00", expense_date=date(YEAR, month, 1))

        context, items = self.build(limit=2)

        self.assertEqual(len(items), 2)
        self.assertEqual(context["grand_total"], Decimal("50.00"))

    def test_yearly_totals_group_by_year(self):
        self.make_expense(amount="100.00", expense_date=date(YEAR, 5, 1))
        self.make_expense(amount="25.00", expense_date=date(YEAR - 1, 5, 1))

        context, _items = self.build()

        totals = {row["date__year"]: row["total"] for row in context["yearly_totals"]}
        self.assertEqual(totals[YEAR], Decimal("100.00"))
        self.assertEqual(totals[YEAR - 1], Decimal("25.00"))

    def test_category_breakdown_is_opt_in(self):
        self.make_expense(amount="100.00", expense_date=date(YEAR, 5, 1), category="office")

        without, _ = self.build()
        with_categories, _ = self.build(include_categories=True)

        self.assertNotIn("category_totals", without)
        self.assertIn("category_totals", with_categories)

    def test_tax_deductible_total_counts_only_deductible_rows(self):
        self.make_expense(amount="100.00", expense_date=date(YEAR, 5, 1))
        self.make_expense(amount="70.00", expense_date=date(YEAR, 5, 2), deductible=False)

        context, _items = self.build(include_tax_deductible=True)

        self.assertEqual(context["tax_deductible_total"], Decimal("100.00"))
        self.assertEqual(context["grand_total"], Decimal("170.00"))

    def test_apply_year_filter_is_reusable_for_a_second_queryset(self):
        self.make_expense(amount="100.00", expense_date=date(YEAR, 5, 1))
        self.make_expense(amount="50.00", expense_date=date(YEAR - 1, 5, 1))
        qs = CompanyExpense.objects.filter(practice=self.practice)

        self.assertEqual(FinancialListContextBuilder.apply_year_filter(qs, YEAR).count(), 1)
        self.assertEqual(FinancialListContextBuilder.apply_year_filter(qs, None).count(), 2)


# ── AnalyticsDashboardBuilder ─────────────────────────────────────────────────


class AnalyticsDateRangeTest(BuilderTestBase):
    def builder(self, **kwargs):
        return AnalyticsDashboardBuilder(self.make_request(), **kwargs)

    def test_month_period_spans_the_last_month(self):
        builder = self.builder(period="month")
        builder._parse_date_range()

        self.assertEqual(builder.end_date, builder.today)
        self.assertEqual(builder.start_year, builder.start_date.year)
        self.assertLess(builder.start_date, builder.end_date)

    def test_custom_period_uses_the_supplied_iso_dates(self):
        builder = self.builder(period="custom", custom_start="2024-02-01", custom_end="2024-04-30")
        builder._parse_date_range()

        self.assertEqual(builder.start_date, date(2024, 2, 1))
        self.assertEqual(builder.end_date, date(2024, 4, 30))
        self.assertEqual(builder.start_year, 2024)

    def test_invalid_custom_dates_fall_back_to_all_time(self):
        builder = self.builder(period="custom", custom_start="not-a-date", custom_end="2024-04-30")
        builder._parse_date_range()

        self.assertEqual(builder.period, "all")
        self.assertIsNone(builder.start_date)
        self.assertIsNone(builder.end_date)

    def test_custom_period_without_dates_falls_back_to_all_time(self):
        builder = self.builder(period="custom")
        builder._parse_date_range()

        self.assertEqual(builder.period, "all")

    def test_unknown_period_falls_back_to_all_time(self):
        builder = self.builder(period="fortnight")
        builder._parse_date_range()

        self.assertEqual(builder.period, "all")

    def test_filter_data_exposes_dates_only_for_custom_periods(self):
        custom = self.builder(period="custom", custom_start="2024-02-01", custom_end="2024-04-30")
        custom._parse_date_range()
        self.assertEqual(custom._get_filter_data()["start_date"], "2024-02-01")

        month = self.builder(period="month")
        month._parse_date_range()
        self.assertEqual(month._get_filter_data()["start_date"], "")
        self.assertEqual(month._get_filter_data()["selected_period"], "month")


class AnalyticsEarliestDataYearTest(BuilderTestBase):
    def earliest(self, practice=None):
        builder = AnalyticsDashboardBuilder(self.make_request(practice))
        return builder._get_earliest_data_year()

    def test_falls_back_to_the_current_year_without_data(self):
        self.assertEqual(self.earliest(), date.today().year)

    def test_takes_the_minimum_across_invoices_expenses_and_withdrawals(self):
        self.make_invoice(invoice_date=date(2021, 6, 1))
        CompanyExpense.objects.create(
            practice=self.practice,
            amount=Decimal("10"),
            date=date(2019, 6, 1),
            category="other",
            description="x",
        )
        CompanyWithdrawal.objects.create(
            practice=self.practice,
            amount=Decimal("10"),
            date=date(2023, 6, 1),
            category="withdrawal",
        )

        self.assertEqual(self.earliest(), 2019)

    def test_other_practices_data_does_not_move_the_start_year(self):
        other = Practice.objects.create(name="Other", slug="rb-other")
        CompanyExpense.objects.create(
            practice=other,
            amount=Decimal("10"),
            date=date(2005, 6, 1),
            category="other",
            description="x",
        )
        self.make_invoice(invoice_date=date(2021, 6, 1))

        self.assertEqual(self.earliest(), 2021)


class AnalyticsSeasonalityTest(BuilderTestBase):
    """_get_seasonality_from_capacity reshapes capacity trends — a pure function."""

    def seasonality(self, trends):
        return AnalyticsDashboardBuilder(self.make_request())._get_seasonality_from_capacity(trends)

    @staticmethod
    def trend(year, month, booked, capacity=100.0, pct=50):
        return {
            "year": year,
            "month_num": month,
            "booked_hours": booked,
            "capacity_hours": capacity,
            "capacity_percentage": pct,
        }

    def test_always_returns_twelve_months_january_first(self):
        result = self.seasonality([])

        self.assertEqual(len(result), 12)
        self.assertEqual([r["month_num"] for r in result], list(range(1, 13)))

    def test_months_without_bookings_report_zero_years(self):
        result = self.seasonality([self.trend(2025, 3, booked=10.0)])

        march = result[2]
        january = result[0]
        self.assertEqual(march["years_count"], 1)
        self.assertEqual(january["years_count"], 0)
        self.assertEqual(january["avg_capacity_pct"], 0)

    def test_averages_across_years_for_the_same_month(self):
        result = self.seasonality(
            [
                self.trend(2024, 3, booked=10.0, pct=40),
                self.trend(2025, 3, booked=20.0, pct=60),
            ]
        )

        march = result[2]
        self.assertEqual(march["years_count"], 2)
        self.assertEqual(march["avg_booked_hours"], 15.0)
        self.assertEqual(march["avg_capacity_pct"], 50)

    def test_zero_booked_months_are_excluded_from_the_average(self):
        """A vacation month must not drag the seasonal average down."""
        result = self.seasonality(
            [
                self.trend(2024, 3, booked=0.0, pct=0),
                self.trend(2025, 3, booked=20.0, pct=60),
            ]
        )

        march = result[2]
        self.assertEqual(march["years_count"], 1)
        self.assertEqual(march["avg_booked_hours"], 20.0)
        self.assertEqual(march["avg_capacity_pct"], 60)


class AnalyticsCumulativeYearDataTest(BuilderTestBase):
    def cumulative(self, trends):
        return AnalyticsDashboardBuilder(self.make_request())._get_cumulative_year_data(trends)

    @staticmethod
    def trend(year, month, booked):
        return {
            "year": year,
            "month_num": month,
            "booked_hours": booked,
            "capacity_hours": 100.0,
            "capacity_percentage": 50,
        }

    def test_empty_input_yields_an_empty_dict(self):
        self.assertEqual(self.cumulative([]), {})

    def test_each_year_becomes_twelve_slots_with_none_for_missing_months(self):
        result = self.cumulative([self.trend(2025, 3, 10.0)])

        series = result["datasets"]["2025"]
        self.assertEqual(len(series), 12)
        self.assertEqual(series[2], 10.0)
        self.assertIsNone(series[0])

    def test_keeps_only_the_last_four_years(self):
        trends = [self.trend(year, 3, 10.0) for year in range(2019, 2027)]

        result = self.cumulative(trends)

        self.assertEqual(result["years"], [2023, 2024, 2025, 2026])

    def test_average_ignores_missing_months(self):
        result = self.cumulative(
            [
                self.trend(2024, 3, 10.0),
                self.trend(2025, 3, 20.0),
                self.trend(2025, 4, 8.0),
            ]
        )

        self.assertEqual(result["average"][2], 15.0)  # March: both years
        self.assertEqual(result["average"][3], 8.0)  # April: only 2025
        self.assertIsNone(result["average"][0])  # January: neither

    def test_zero_booked_months_are_not_recorded(self):
        result = self.cumulative([self.trend(2025, 3, 0.0), self.trend(2025, 4, 5.0)])

        self.assertIsNone(result["datasets"]["2025"][2])
        self.assertEqual(result["datasets"]["2025"][3], 5.0)


class AnalyticsTimeOffTest(BuilderTestBase):
    def builder(self, **kwargs):
        b = AnalyticsDashboardBuilder(self.make_request(), **kwargs)
        b._parse_date_range()
        return b

    def test_timeoff_by_type_clamps_periods_to_the_year(self):
        TimeOff.objects.create(
            start_date=date(YEAR - 1, 12, 28),
            end_date=date(YEAR, 1, 6),
            title="Weihnachten",
            type="vacation",
        )

        breakdown = self.builder()._get_timeoff_by_type_for_year(YEAR)

        # Only the January portion counts, and only its working days.
        self.assertGreater(breakdown["vacation"], 0)
        self.assertLessEqual(breakdown["vacation"], 5)

    def test_timeoff_types_are_tracked_separately(self):
        TimeOff.objects.create(
            start_date=date(YEAR, 3, 2), end_date=date(YEAR, 3, 3), title="Urlaub", type="vacation"
        )
        TimeOff.objects.create(
            start_date=date(YEAR, 4, 13),
            end_date=date(YEAR, 4, 14),
            title="Fortbildung",
            type="training",
        )

        breakdown = self.builder()._get_timeoff_by_type_for_year(YEAR)

        self.assertEqual(breakdown["vacation"], 2)
        self.assertEqual(breakdown["training"], 2)

    def test_yearly_breakdown_is_newest_first_and_derives_weeks(self):
        TimeOff.objects.create(
            start_date=date(2024, 3, 4), end_date=date(2024, 3, 8), title="Urlaub", type="vacation"
        )
        TimeOff.objects.create(
            start_date=date(2025, 3, 3), end_date=date(2025, 3, 7), title="Urlaub", type="vacation"
        )

        rows = self.builder()._get_yearly_timeoff_breakdown()

        self.assertEqual([r["year"] for r in rows], [2025, 2024])
        self.assertEqual(rows[0]["total_weeks"], round(rows[0]["workdays"] / 5, 1))

    def test_month_period_label_names_the_month(self):
        builder = self.builder(period="month")

        self.assertEqual(builder._generate_timeoff_label(), builder.start_date.strftime("%B %Y"))

    def test_quarter_period_label_is_a_quarter(self):
        builder = self.builder(period="quarter")

        self.assertRegex(builder._generate_timeoff_label(), r"^Q[1-4] \d{4}$")

    def test_full_calendar_year_custom_range_collapses_to_the_year(self):
        builder = self.builder(period="custom", custom_start="2024-01-15", custom_end="2024-12-20")

        self.assertEqual(builder._generate_timeoff_label(), "2024")
