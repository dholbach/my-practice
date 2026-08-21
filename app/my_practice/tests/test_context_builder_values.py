"""
Value-level tests for TaxYearContextBuilder and DashboardContextAssembler.

CLAUDE.md promotes the builder classes as the pattern to follow for complex
context, but they were the least directly-tested layer in the codebase: the
pages they feed are covered by view tests that assert a 200 and a template
name, so "the page renders" was tested while "the numbers are right" was not.
For the tax builder those numbers are tax figures.

These tests therefore assert computed *values* — the money formulas, the
year/status/practice filters that decide what goes into them, and the
multi-practice split ratios — rather than that a context dict came back.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from my_practice.models import (
    Client,
    CompanyExpense,
    Invoice,
    Practice,
    Session,
    TimeOff,
    UserPractice,
)
from my_practice.utils.dashboard_context_builder import DashboardContextAssembler
from my_practice.utils.tax_context_builder import TaxYearContextBuilder, available_data_years

User = get_user_model()

YEAR = 2026


class BuilderTestBase(TestCase):
    """One practice, one user, one client. Subclasses add the data under test."""

    def setUp(self):
        self.user = User.objects.create_user(username="builder-user", password="testpass123")
        self.practice = self.make_practice("Main Practice", "builder-main")
        self.client_a = Client.objects.create(
            client_code="AB-1", full_name="Max Mustermann", practice=self.practice
        )

    def make_practice(self, name, slug, link_user=True):
        practice = Practice.objects.create(name=name, slug=slug, city="Berlin")
        if link_user:
            UserPractice.objects.create(user=self.user, practice=practice, is_owner=True)
        return practice

    def make_invoice(
        self, *, practice=None, client=None, total, status, invoice_date, paid_date=None
    ):
        practice = practice or self.practice
        client = client or self.client_a
        invoice = Invoice.objects.create(
            client=client,
            invoice_number=f"INV-{Invoice.objects.count() + 1:03d}",
            status=status,
            total=Decimal(total),
            practice=practice,
        )
        # Invoice.save() forces invoice_date to today when creating a draft, so
        # the dates under test have to be written afterwards.
        invoice.invoice_date = invoice_date
        invoice.paid_date = paid_date
        invoice.save(update_fields=["invoice_date", "paid_date"])
        return invoice

    def make_expense(self, *, practice=None, amount, expense_date, deductible=True):
        return CompanyExpense.objects.create(
            practice=practice or self.practice,
            amount=Decimal(amount),
            date=expense_date,
            category="other",
            description="Test expense",
            is_tax_deductible=deductible,
        )

    def configure_deductions(self, weekdays=(0, 1, 2), distance_km=10, session_count=3):
        """Make both deductions claimable.

        Fahrtkosten is computed from *actual session days* (§9: days you drove),
        not calendar days, so configuring the practice alone yields zero — real
        Session rows on the configured weekdays are required. Home office is
        calendar-based over the complementary weekdays and needs no sessions.
        """
        self.practice.commute_distance_km = distance_km
        self.practice.practice_weekdays = list(weekdays)
        self.practice.save(update_fields=["commute_distance_km", "practice_weekdays"])

        current, made = date(YEAR, 3, 1), 0
        while made < session_count:
            if current.weekday() in weekdays:
                Session.objects.create(client=self.client_a, session_date=current)
                made += 1
            current += timedelta(days=1)


# ── TaxYearContextBuilder ─────────────────────────────────────────────────────


class TaxYearRevenueTest(BuilderTestBase):
    def test_only_paid_invoices_count_towards_revenue(self):
        paid = self.make_invoice(
            total="100.00", status="paid", invoice_date=date(YEAR, 3, 1), paid_date=date(YEAR, 3, 5)
        )
        self.make_invoice(total="500.00", status="sent", invoice_date=date(YEAR, 3, 1))
        self.make_invoice(total="900.00", status="draft", invoice_date=date(YEAR, 3, 1))

        context = TaxYearContextBuilder(YEAR, self.practice, self.user).build()

        self.assertEqual(context["total_revenue"], Decimal("100.00"))
        self.assertEqual(context["invoice_count"], 1)
        # total_revenue comes from RevenueCalculator while paid_invoices and
        # monthly_revenue are built from a separate queryset here — assert both,
        # or a filter drifting apart between them goes unnoticed.
        self.assertEqual([i.pk for i in context["paid_invoices"]], [paid.pk])
        self.assertEqual([m["amount"] for m in context["monthly_revenue"]], [Decimal("100.00")])

    def test_revenue_is_bucketed_by_paid_date_not_invoice_date(self):
        """An invoice raised in December but paid in January belongs to the later year."""
        self.make_invoice(
            total="250.00",
            status="paid",
            invoice_date=date(YEAR - 1, 12, 20),
            paid_date=date(YEAR, 1, 8),
        )

        prior = TaxYearContextBuilder(YEAR - 1, self.practice, self.user).build()
        current = TaxYearContextBuilder(YEAR, self.practice, self.user).build()

        self.assertEqual(prior["total_revenue"], Decimal("0"))
        self.assertEqual(current["total_revenue"], Decimal("250.00"))

    def test_other_practices_revenue_is_excluded(self):
        other = self.make_practice("Coaching", "builder-other")
        other_client = Client.objects.create(
            client_code="CD-2", full_name="Anna Schmidt", practice=other
        )
        self.make_invoice(
            total="100.00", status="paid", invoice_date=date(YEAR, 3, 1), paid_date=date(YEAR, 3, 5)
        )
        self.make_invoice(
            practice=other,
            client=other_client,
            total="7777.00",
            status="paid",
            invoice_date=date(YEAR, 3, 1),
            paid_date=date(YEAR, 3, 5),
        )

        context = TaxYearContextBuilder(YEAR, self.practice, self.user).build()

        self.assertEqual(context["total_revenue"], Decimal("100.00"))

    def test_monthly_revenue_groups_and_sums_by_payment_month(self):
        self.make_invoice(
            total="100.00", status="paid", invoice_date=date(YEAR, 3, 1), paid_date=date(YEAR, 3, 5)
        )
        self.make_invoice(
            total="50.00", status="paid", invoice_date=date(YEAR, 3, 2), paid_date=date(YEAR, 3, 20)
        )
        self.make_invoice(
            total="70.00", status="paid", invoice_date=date(YEAR, 5, 1), paid_date=date(YEAR, 5, 9)
        )

        monthly = TaxYearContextBuilder(YEAR, self.practice, self.user).build()["monthly_revenue"]

        self.assertEqual(len(monthly), 2)
        self.assertEqual(monthly[0]["amount"], Decimal("150.00"))
        self.assertEqual(monthly[0]["count"], 2)
        self.assertEqual(monthly[1]["amount"], Decimal("70.00"))
        self.assertEqual(monthly[1]["count"], 1)

    def test_monthly_revenue_is_chronological_regardless_of_insertion_order(self):
        # Created Nov, Feb, Jul — must come back Feb, Jul, Nov.
        for month, amount in ((11, "30.00"), (2, "10.00"), (7, "20.00")):
            self.make_invoice(
                total=amount,
                status="paid",
                invoice_date=date(YEAR, month, 1),
                paid_date=date(YEAR, month, 2),
            )

        monthly = TaxYearContextBuilder(YEAR, self.practice, self.user).build()["monthly_revenue"]

        self.assertEqual(
            [m["amount"] for m in monthly],
            [Decimal("10.00"), Decimal("20.00"), Decimal("30.00")],
        )


class TaxYearExpenseTest(BuilderTestBase):
    def test_only_tax_deductible_expenses_count(self):
        self.make_expense(amount="100.00", expense_date=date(YEAR, 4, 1))
        self.make_expense(amount="900.00", expense_date=date(YEAR, 4, 1), deductible=False)

        context = TaxYearContextBuilder(YEAR, self.practice, self.user).build()

        self.assertEqual(Decimal(context["total_expenses"]), Decimal("100.00"))
        self.assertEqual(context["expense_count"], 1)

    def test_expenses_outside_the_year_are_excluded(self):
        self.make_expense(amount="100.00", expense_date=date(YEAR, 1, 1))
        self.make_expense(amount="800.00", expense_date=date(YEAR - 1, 12, 31))
        self.make_expense(amount="800.00", expense_date=date(YEAR + 1, 1, 1))

        context = TaxYearContextBuilder(YEAR, self.practice, self.user).build()

        self.assertEqual(Decimal(context["total_expenses"]), Decimal("100.00"))

    def test_other_practices_expenses_are_excluded(self):
        other = self.make_practice("Coaching", "builder-other-exp")
        self.make_expense(amount="100.00", expense_date=date(YEAR, 4, 1))
        self.make_expense(practice=other, amount="4242.00", expense_date=date(YEAR, 4, 1))

        context = TaxYearContextBuilder(YEAR, self.practice, self.user).build()

        self.assertEqual(Decimal(context["total_expenses"]), Decimal("100.00"))

    def test_se_sort_groups_already_filed_expenses_first(self):
        """`-is_filed_in_tax_return` is descending — filed first, matching the "SE ↓" header."""
        # Deliberately give the filed one the earlier date, so date ordering alone
        # would produce the same result and prove nothing; the unfiled one is later.
        filed = self.make_expense(amount="10.00", expense_date=date(YEAR, 6, 5))
        filed.is_filed_in_tax_return = True
        filed.save(update_fields=["is_filed_in_tax_return"])
        unfiled = self.make_expense(amount="20.00", expense_date=date(YEAR, 1, 5))

        context = TaxYearContextBuilder(YEAR, self.practice, self.user).build(expense_sort="se")

        self.assertEqual([e.pk for e in context["expenses"]], [filed.pk, unfiled.pk])
        self.assertEqual(context["expense_sort"], "se")

    def test_default_sort_is_by_date(self):
        later = self.make_expense(amount="20.00", expense_date=date(YEAR, 6, 5))
        earlier = self.make_expense(amount="10.00", expense_date=date(YEAR, 1, 5))

        context = TaxYearContextBuilder(YEAR, self.practice, self.user).build()

        self.assertEqual([e.pk for e in context["expenses"]], [earlier.pk, later.pk])
        self.assertEqual(context["expense_sort"], "date")


class TaxYearGrossProfitTest(BuilderTestBase):
    """gross_profit = revenue − expenses − Fahrtkosten − home office."""

    def test_revenue_minus_expenses_when_no_deductions_configured(self):
        self.make_invoice(
            total="1000.00",
            status="paid",
            invoice_date=date(YEAR, 3, 1),
            paid_date=date(YEAR, 3, 5),
        )
        self.make_expense(amount="250.00", expense_date=date(YEAR, 4, 1))

        context = TaxYearContextBuilder(YEAR, self.practice, self.user).build()

        # An unconfigured practice claims neither deduction.
        self.assertEqual(context["fahrtkosten_deduction"], Decimal("0"))
        self.assertEqual(context["home_office_deduction"], Decimal("0"))
        self.assertEqual(context["gross_profit"], Decimal("750.00"))

    def test_deductions_are_subtracted_from_gross_profit(self):
        self.configure_deductions()
        self.make_invoice(
            total="1000.00",
            status="paid",
            invoice_date=date(YEAR, 3, 1),
            paid_date=date(YEAR, 3, 5),
        )
        self.make_expense(amount="250.00", expense_date=date(YEAR, 4, 1))

        context = TaxYearContextBuilder(YEAR, self.practice, self.user).build()

        # Configuring the practice must actually claim something...
        self.assertGreater(context["fahrtkosten_deduction"], Decimal("0"))
        self.assertGreater(context["home_office_deduction"], Decimal("0"))
        # ...and gross_profit must account for both, not just revenue − expenses.
        self.assertEqual(
            context["gross_profit"],
            Decimal("1000.00")
            - Decimal("250.00")
            - context["fahrtkosten_deduction"]
            - context["home_office_deduction"],
        )
        self.assertLess(context["gross_profit"], Decimal("750.00"))

    def test_gross_profit_can_be_negative(self):
        self.make_expense(amount="500.00", expense_date=date(YEAR, 4, 1))

        context = TaxYearContextBuilder(YEAR, self.practice, self.user).build()

        self.assertEqual(context["gross_profit"], Decimal("-500.00"))


class TaxYearPracticeSplitTest(BuilderTestBase):
    """The multi-practice allocation ratios shown on the tax page."""

    def test_no_split_for_a_single_practice(self):
        context = TaxYearContextBuilder(YEAR, self.practice, self.user).build()

        self.assertIsNone(context["practice_split"])
        self.assertFalse(context["show_multi_practice_allocation_notice"])
        self.assertIsNone(context["revenue_share_pct"])

    def _two_practice_setup(self):
        self.other = self.make_practice("Coaching", "builder-split-other")
        self.other_client = Client.objects.create(
            client_code="CD-2", full_name="Anna Schmidt", practice=self.other
        )

    def test_revenue_share_is_this_practices_fraction_of_the_total(self):
        self._two_practice_setup()
        self.make_invoice(
            total="750.00", status="paid", invoice_date=date(YEAR, 3, 1), paid_date=date(YEAR, 3, 5)
        )
        self.make_invoice(
            practice=self.other,
            client=self.other_client,
            total="250.00",
            status="paid",
            invoice_date=date(YEAR, 3, 1),
            paid_date=date(YEAR, 3, 5),
        )

        context = TaxYearContextBuilder(YEAR, self.practice, self.user).build()
        split = context["practice_split"]

        self.assertEqual(split.this_revenue, Decimal("750.00"))
        self.assertEqual(split.total_revenue_all, Decimal("1000.00"))
        self.assertEqual(split.revenue_share, Decimal("0.7500"))
        self.assertEqual(context["revenue_share_pct"], Decimal("75.0"))
        self.assertTrue(context["show_multi_practice_allocation_notice"])

    def test_session_share_counts_distinct_days_not_sessions(self):
        self._two_practice_setup()
        # Three sessions for this practice but on only two distinct days.
        for day in (3, 3, 10):
            Session.objects.create(client=self.client_a, session_date=date(YEAR, 4, day))
        Session.objects.create(client=self.other_client, session_date=date(YEAR, 4, 17))

        split = TaxYearContextBuilder(YEAR, self.practice, self.user).build()["practice_split"]

        self.assertEqual(split.this_session_days, 2)
        self.assertEqual(split.total_session_days_all, 3)

    def test_cancelled_sessions_do_not_count(self):
        self._two_practice_setup()
        Session.objects.create(client=self.client_a, session_date=date(YEAR, 4, 3))
        Session.objects.create(client=self.client_a, session_date=date(YEAR, 4, 10), cancelled=True)

        split = TaxYearContextBuilder(YEAR, self.practice, self.user).build()["practice_split"]

        self.assertEqual(split.this_session_days, 1)

    def test_shares_fall_back_to_one_when_nothing_to_split(self):
        """Zero revenue across all practices must not divide by zero."""
        self._two_practice_setup()

        split = TaxYearContextBuilder(YEAR, self.practice, self.user).build()["practice_split"]

        self.assertEqual(split.revenue_share, Decimal("1"))
        self.assertEqual(split.session_share, Decimal("1"))

    def test_deductions_are_apportioned_by_both_ratios(self):
        self._two_practice_setup()
        self.configure_deductions()
        self.make_invoice(
            total="750.00", status="paid", invoice_date=date(YEAR, 3, 1), paid_date=date(YEAR, 3, 5)
        )
        self.make_invoice(
            practice=self.other,
            client=self.other_client,
            total="250.00",
            status="paid",
            invoice_date=date(YEAR, 3, 1),
            paid_date=date(YEAR, 3, 5),
        )

        context = TaxYearContextBuilder(YEAR, self.practice, self.user).build()

        # build() must run _build_deductions() before _build_split_context(),
        # otherwise these are silently apportioned from zero.
        expected = (context["home_office_deduction"] * Decimal("0.7500")).quantize(Decimal("0.01"))
        self.assertEqual(context["home_office_split_revenue"], expected)
        self.assertGreater(context["home_office_split_revenue"], Decimal("0"))
        self.assertGreater(context["fahrtkosten_split_revenue"], Decimal("0"))

    def test_inactive_practices_are_not_part_of_the_split(self):
        self._two_practice_setup()
        self.other.is_active = False
        self.other.save(update_fields=["is_active"])

        context = TaxYearContextBuilder(YEAR, self.practice, self.user).build()

        self.assertIsNone(context["practice_split"])
        self.assertEqual(context["active_practice_count"], 1)


class AvailableDataYearsTest(BuilderTestBase):
    def test_descending_and_merges_invoice_and_expense_years(self):
        self.make_invoice(
            total="10.00", status="paid", invoice_date=date(2024, 5, 1), paid_date=date(2024, 5, 2)
        )
        self.make_expense(amount="10.00", expense_date=date(2026, 5, 1))

        self.assertEqual(available_data_years(self.practice), [2026, 2024])

    def test_expenses_can_be_excluded(self):
        self.make_invoice(
            total="10.00", status="paid", invoice_date=date(2024, 5, 1), paid_date=date(2024, 5, 2)
        )
        self.make_expense(amount="10.00", expense_date=date(2026, 5, 1))

        self.assertEqual(available_data_years(self.practice, include_expenses=False), [2024])

    def test_other_practices_years_are_excluded(self):
        other = self.make_practice("Coaching", "builder-years-other")
        self.make_expense(practice=other, amount="10.00", expense_date=date(2019, 5, 1))

        self.assertNotIn(2019, available_data_years(self.practice))


# ── DashboardContextAssembler ─────────────────────────────────────────────────


class DashboardBuilderTestBase(BuilderTestBase):
    def build_dashboard(self, today=None, practice=None):
        request = RequestFactory().get("/")
        request.user = self.user
        request.current_practice = practice if practice is not None else self.practice
        return DashboardContextAssembler(request, today=today or date(YEAR, 6, 15)).build()


class DashboardStatisticsTest(DashboardBuilderTestBase):
    def test_year_profit_is_revenue_minus_expenses(self):
        self.make_invoice(
            total="1000.00",
            status="paid",
            invoice_date=date(YEAR, 3, 1),
            paid_date=date(YEAR, 3, 5),
        )
        self.make_expense(amount="400.00", expense_date=date(YEAR, 4, 1))

        context = self.build_dashboard()

        self.assertEqual(context["year_revenue"], Decimal("1000.00"))
        self.assertEqual(context["year_expenses"], Decimal("400.00"))
        self.assertEqual(context["year_profit"], Decimal("600.00"))

    def test_year_expenses_include_non_deductible_ones(self):
        """Unlike the tax view, the dashboard shows real cash out, deductible or not."""
        self.make_expense(amount="100.00", expense_date=date(YEAR, 4, 1))
        self.make_expense(amount="50.00", expense_date=date(YEAR, 4, 2), deductible=False)

        self.assertEqual(self.build_dashboard()["year_expenses"], Decimal("150.00"))

    def test_expenses_from_other_years_excluded(self):
        self.make_expense(amount="100.00", expense_date=date(YEAR, 4, 1))
        self.make_expense(amount="999.00", expense_date=date(YEAR - 1, 4, 1))

        self.assertEqual(self.build_dashboard()["year_expenses"], Decimal("100.00"))

    def test_unpaid_figures_come_from_sent_invoices(self):
        self.make_invoice(total="300.00", status="sent", invoice_date=date(YEAR, 5, 1))
        self.make_invoice(total="200.00", status="sent", invoice_date=date(YEAR, 5, 2))
        self.make_invoice(
            total="900.00", status="paid", invoice_date=date(YEAR, 5, 3), paid_date=date(YEAR, 5, 4)
        )

        context = self.build_dashboard()

        self.assertEqual(context["unpaid_value"], Decimal("500.00"))
        self.assertEqual(context["unpaid_count"], 2)

    def test_active_clients_counts_only_clients_with_invoices_once_each(self):
        Client.objects.create(client_code="ZZ-9", full_name="No Invoices", practice=self.practice)
        self.make_invoice(
            total="10.00", status="paid", invoice_date=date(YEAR, 5, 1), paid_date=date(YEAR, 5, 2)
        )
        self.make_invoice(
            total="20.00", status="paid", invoice_date=date(YEAR, 5, 3), paid_date=date(YEAR, 5, 4)
        )

        self.assertEqual(self.build_dashboard()["active_clients"], 1)

    def test_recent_invoices_capped_at_ten_newest_first(self):
        for day in range(1, 13):
            self.make_invoice(total="10.00", status="sent", invoice_date=date(YEAR, 5, day))

        recent = list(self.build_dashboard()["recent_invoices"])

        self.assertEqual(len(recent), 10)
        self.assertEqual(recent[0].invoice_date, date(YEAR, 5, 12))
        self.assertGreater(recent[0].invoice_date, recent[-1].invoice_date)

    def test_statistics_are_scoped_to_the_current_practice(self):
        other = self.make_practice("Coaching", "dash-other")
        other_client = Client.objects.create(
            client_code="CD-2", full_name="Anna Schmidt", practice=other
        )
        self.make_invoice(
            total="100.00", status="paid", invoice_date=date(YEAR, 3, 1), paid_date=date(YEAR, 3, 5)
        )
        self.make_invoice(
            practice=other,
            client=other_client,
            total="8888.00",
            status="paid",
            invoice_date=date(YEAR, 3, 1),
            paid_date=date(YEAR, 3, 5),
        )
        self.make_expense(practice=other, amount="777.00", expense_date=date(YEAR, 4, 1))

        context = self.build_dashboard()

        self.assertEqual(context["total_invoices"], 1)
        self.assertEqual(context["year_revenue"], Decimal("100.00"))
        self.assertEqual(context["year_expenses"], Decimal("0"))
        self.assertEqual(context["active_clients"], 1)

    def test_month_revenue_covers_only_the_current_month(self):
        self.make_invoice(
            total="60.00", status="paid", invoice_date=date(YEAR, 6, 2), paid_date=date(YEAR, 6, 3)
        )
        self.make_invoice(
            total="900.00", status="paid", invoice_date=date(YEAR, 5, 2), paid_date=date(YEAR, 5, 3)
        )

        context = self.build_dashboard(today=date(YEAR, 6, 15))

        self.assertEqual(context["month_revenue"], Decimal("60.00"))
        self.assertEqual(context["month_count"], 1)

    def test_current_year_follows_the_supplied_today(self):
        self.assertEqual(self.build_dashboard(today=date(2029, 2, 1))["current_year"], 2029)


class DashboardTimeOffTest(DashboardBuilderTestBase):
    def test_current_timeoff_is_the_period_containing_today(self):
        today = date(YEAR, 6, 15)
        ongoing = TimeOff.objects.create(
            start_date=today - timedelta(days=2), end_date=today + timedelta(days=2), title="Urlaub"
        )
        TimeOff.objects.create(
            start_date=today + timedelta(days=30),
            end_date=today + timedelta(days=35),
            title="Später",
        )

        context = self.build_dashboard(today=today)

        self.assertEqual(context["current_timeoff"].pk, ongoing.pk)

    def test_upcoming_timeoff_is_the_next_one_starting_after_today(self):
        today = date(YEAR, 6, 15)
        TimeOff.objects.create(
            start_date=today + timedelta(days=40), end_date=today + timedelta(days=45), title="Fern"
        )
        soonest = TimeOff.objects.create(
            start_date=today + timedelta(days=10), end_date=today + timedelta(days=12), title="Bald"
        )

        context = self.build_dashboard(today=today)

        self.assertEqual(context["upcoming_timeoff"].pk, soonest.pk)

    def test_no_timeoff_yields_none_rather_than_raising(self):
        context = self.build_dashboard()

        self.assertIsNone(context["current_timeoff"])
        self.assertIsNone(context["upcoming_timeoff"])


class DashboardMultiPracticeTest(DashboardBuilderTestBase):
    def test_single_practice_gets_no_comparison_table(self):
        self.assertEqual(self.build_dashboard()["practice_stats"], [])

    def test_multi_practice_stats_are_per_practice_and_flag_the_current_one(self):
        other = self.make_practice("Coaching", "dash-multi-other")
        other_client = Client.objects.create(
            client_code="CD-2", full_name="Anna Schmidt", practice=other
        )
        self.make_invoice(
            total="100.00", status="paid", invoice_date=date(YEAR, 3, 1), paid_date=date(YEAR, 3, 5)
        )
        self.make_invoice(
            practice=other,
            client=other_client,
            total="400.00",
            status="paid",
            invoice_date=date(YEAR, 3, 1),
            paid_date=date(YEAR, 3, 5),
        )

        stats = {s["practice"].slug: s for s in self.build_dashboard()["practice_stats"]}

        self.assertEqual(stats["builder-main"]["revenue"], Decimal("100.00"))
        self.assertEqual(stats["dash-multi-other"]["revenue"], Decimal("400.00"))
        self.assertTrue(stats["builder-main"]["is_current"])
        self.assertFalse(stats["dash-multi-other"]["is_current"])

    def test_practice_stats_invoice_count_uses_invoice_date_year(self):
        self.make_practice("Coaching", "dash-count-other")
        self.make_invoice(total="10.00", status="sent", invoice_date=date(YEAR, 3, 1))
        self.make_invoice(total="10.00", status="sent", invoice_date=date(YEAR - 1, 3, 1))

        stats = {s["practice"].slug: s for s in self.build_dashboard()["practice_stats"]}

        self.assertEqual(stats["builder-main"]["invoice_count"], 1)
