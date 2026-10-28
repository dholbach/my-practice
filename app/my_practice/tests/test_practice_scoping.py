"""Practice scoping fails closed.

Query helpers used to take ``practice=None`` and filter with
``if practice: qs = qs.filter(practice=practice)``. ``request.current_practice``
is None for a user who belongs to no practice, so that user was shown every
practice's revenue, expenses, clients and capacity — and two analytics view
tests only passed because of it (their user was never linked to a practice).

Now ``practice`` is a required keyword argument, None means "nothing", and a
caller that really wants every practice says so with ALL_PRACTICES.
"""

import ast
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ..models import (
    ALL_PRACTICES,
    Client,
    CompanyExpense,
    Invoice,
    MarketingPeriod,
    Practice,
    UserPractice,
    scope_to_practice,
)
from ..utils import RevenueCalculator
from ..utils.analytics_utils import ClientAnalyzer, ExpenseAnalyzer, RevenueAnalyzer
from ..utils.practice_analysis import PracticeAnalyzer
from ..views.crud_mixins import (
    PracticeScopedDeleteView,
    PracticeScopedListView,
    PracticeScopedUpdateView,
)
from .test_helpers import create_test_practice, link_user_to_practice

APP_DIR = Path(settings.BASE_DIR) / "my_practice"

# Functions that may take practice=None on purpose. A Google Calendar token
# without a practice is the documented single-practice fallback
# (models/calendar.py), not a query over practice data.
KNOWN_OPTIONAL_PRACTICE = frozenset(
    {
        "utils/google_calendar.py:save_token",
        "utils/google_calendar.py:get_active_token",
        "utils/google_calendar.py:get_service",
    }
)

# The calendar token lookup falls back to the practice-less token on purpose.
KNOWN_FAIL_OPEN_FILES = frozenset({"utils/google_calendar.py"})

# `if practice:` guarding a filter, or `{...: practice} if practice else {}` —
# both hand out unfiltered data when practice is None.
FAIL_OPEN_PATTERNS = (
    re.compile(r"if (self\.)?practice(\s+is not None)?:\n\s+\w+ = \w+\.filter\("),
    re.compile(r"\{[^{}]*:\s*(self\.)?practice\}\s+if\s+(self\.)?practice\s+else\s+\{\}"),
)


def _source_files():
    """App code that queries practice data. Forms are left out: their practice
    only sets a dropdown's queryset, which has no rows at all until one is given."""
    for path in sorted(APP_DIR.rglob("*.py")):
        rel = str(path.relative_to(APP_DIR)).replace("\\", "/")
        if rel.startswith(("tests/", "migrations/")) or rel.endswith("forms.py"):
            continue
        yield rel, path.read_text()


class FailOpenGuardrailTests(SimpleTestCase):
    def test_no_query_helper_defaults_practice_to_none(self):
        offenders = []
        for rel, source in _source_files():
            for node in ast.walk(ast.parse(source)):
                if not isinstance(node, ast.FunctionDef):
                    continue
                args = node.args
                positional = list(zip(reversed(args.args), reversed(args.defaults), strict=False))
                keyword = list(zip(args.kwonlyargs, args.kw_defaults, strict=True))
                for arg, default in positional + keyword:
                    if (
                        arg.arg == "practice"
                        and isinstance(default, ast.Constant)
                        and default.value is None
                        and f"{rel}:{node.name}" not in KNOWN_OPTIONAL_PRACTICE
                    ):
                        offenders.append(f"{rel}:{node.lineno} {node.name}")
        self.assertEqual(
            offenders,
            [],
            "Make practice a required keyword (`*, practice: PracticeScope`) and "
            "filter with scope_to_practice().",
        )

    def test_no_fail_open_practice_filters(self):
        offenders = []
        for rel, source in _source_files():
            if rel in KNOWN_FAIL_OPEN_FILES:
                continue
            offenders.extend(
                f"{rel}:{source.count(chr(10), 0, match.start()) + 1}"
                for pattern in FAIL_OPEN_PATTERNS
                for match in pattern.finditer(source)
            )
        self.assertEqual(offenders, [], "Use scope_to_practice(), which returns nothing for None.")


class ScopeToPracticeTests(TestCase):
    def setUp(self):
        self.a = Practice.objects.create(name="A", slug="scope-a", title="T")
        self.b = Practice.objects.create(name="B", slug="scope-b", title="T")
        Client.objects.create(client_code="XX", full_name="Max Mustermann", practice=self.a)
        Client.objects.create(client_code="YY", full_name="Anna Schmidt", practice=self.b)

    def test_practice_none_and_all(self):
        qs = Client.objects.all()
        self.assertEqual([c.client_code for c in scope_to_practice(qs, self.a)], ["XX"])
        self.assertEqual(scope_to_practice(qs, None).count(), 0)
        self.assertEqual(scope_to_practice(qs, ALL_PRACTICES).count(), 2)

    def test_related_field(self):
        Invoice.objects.create(
            practice=self.b,
            client=Client.objects.get(client_code="YY"),
            invoice_number="YY-1",
        )
        qs = Invoice.objects.all()
        self.assertEqual(scope_to_practice(qs, self.a, "client__practice").count(), 0)
        self.assertEqual(scope_to_practice(qs, self.b, "client__practice").count(), 1)


class NoPracticeSeesNothingTests(TestCase):
    """A user without a practice gets empty figures, not another practice's."""

    def setUp(self):
        self.practice = Practice.objects.create(name="A", slug="scope-data", title="T")
        client = Client.objects.create(
            client_code="XX", full_name="Max Mustermann", practice=self.practice
        )
        today = date.today()
        Invoice.objects.create(
            practice=self.practice,
            client=client,
            invoice_number="XX-1",
            status="paid",
            paid_date=today,
            total=Decimal("500.00"),
        )
        CompanyExpense.objects.create(practice=self.practice, date=today, amount=Decimal("100.00"))
        self.year = today.year

    def test_helpers_return_nothing_for_none(self):
        self.assertEqual(RevenueCalculator.get_year_revenue(self.year, practice=None)["total"], 0)
        self.assertEqual(
            sum(
                m["revenue"]
                for m in RevenueAnalyzer.get_monthly_trends(start_year=self.year, practice=None)
            ),
            0,
        )
        self.assertEqual(ExpenseAnalyzer.get_expense_breakdown(practice=None)["total"], 0)
        self.assertEqual(ClientAnalyzer.get_top_by_revenue(practice=None), [])
        start, end = date(self.year, 1, 1), date(self.year, 12, 31)
        self.assertEqual(
            PracticeAnalyzer(start, end, practice=None).analyze()["clients"]["total"], 0
        )

    def test_helpers_still_see_their_own_practice_and_all(self):
        for scope in (self.practice, ALL_PRACTICES):
            with self.subTest(scope=scope):
                self.assertEqual(
                    RevenueCalculator.get_year_revenue(self.year, practice=scope)["total"],
                    Decimal("500.00"),
                )

    def test_analytics_page_for_user_without_practice_shows_no_clients(self):
        User.objects.create_user(username="nopractice", password="testpass123")
        self.client.login(username="nopractice", password="testpass123")

        response = self.client.get(reverse("analytics"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["top_clients"], [])

    def test_analytics_page_for_member_shows_its_clients(self):
        user = User.objects.create_user(username="member", password="testpass123")
        UserPractice.objects.create(user=user, practice=self.practice, is_owner=True)
        self.client.login(username="member", password="testpass123")

        response = self.client.get(reverse("analytics"))

        self.assertEqual(
            [row["client"].client_code for row in response.context["top_clients"]], ["XX"]
        )


def _subclasses(cls):
    for sub in cls.__subclasses__():
        yield sub
        yield from _subclasses(sub)


class ScopedViewGuardrailTests(SimpleTestCase):
    def test_every_scoped_view_model_with_a_practice_can_be_scoped(self):
        # The mixins used to skip scoping silently when the model's queryset had
        # no for_current_practice, which let MarketingPeriod be edited across
        # practices. They now raise instead; this catches it before a request does.
        import my_practice.urls  # noqa: F401  (imports every view module)

        offenders = []
        for base in (PracticeScopedListView, PracticeScopedUpdateView, PracticeScopedDeleteView):
            for view in _subclasses(base):
                model = getattr(view, "model", None)
                if model is None:
                    continue
                has_practice = any(f.name == "practice" for f in model._meta.get_fields())
                if has_practice and not hasattr(
                    model._default_manager.all(), "for_current_practice"
                ):
                    offenders.append(f"{view.__name__} ({model.__name__})")
        self.assertEqual(offenders, [])


class MarketingPeriodScopingTests(TestCase):
    def setUp(self):
        other = create_test_practice(name="Test GmbH", slug="test-gmbh")
        self.period = MarketingPeriod.objects.create(
            practice=other, start_date=date(2026, 1, 1), description="XX-1 test period"
        )
        user = User.objects.create_user(username="member", password="testpass123")
        link_user_to_practice(user, create_test_practice(name="Own Practice", slug="own"))
        self.client.login(username="member", password="testpass123")

    def test_other_practices_period_cannot_be_viewed_or_edited(self):
        url = reverse("marketing_period_edit", args=[self.period.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.post(url, {"description": "changed", "start_date": "2026-01-01"})
        self.period.refresh_from_db()
        self.assertEqual(self.period.description, "XX-1 test period")

    def test_other_practices_period_cannot_be_deleted(self):
        url = reverse("marketing_period_delete", args=[self.period.pk])
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(MarketingPeriod.objects.filter(pk=self.period.pk).exists())
