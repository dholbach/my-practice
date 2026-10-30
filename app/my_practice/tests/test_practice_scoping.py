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
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ..models import (
    ALL_PRACTICES,
    Client,
    ClientTag,
    CompanyExpense,
    Invoice,
    MarketingPeriod,
    Practice,
    Session,
    UserPractice,
    scope_to_practice,
)
from ..utils import RevenueCalculator, annotate_client_counts
from ..utils.analytics_utils import ClientAnalyzer, ExpenseAnalyzer, RevenueAnalyzer
from ..utils.capacity_helpers import calculate_period_capacity
from ..utils.practice_analysis import PracticeAnalyzer
from ..utils.practice_days import PracticeDayCalculator
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

KNOWN_FAIL_OPEN_FILES: frozenset[str] = frozenset()

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


# Practice-owned models a helper must not query without binding them to a
# practice — directly, or through a client, invoice or session it was given.
PRACTICE_OWNED_MODELS = frozenset(
    {
        "BankTransaction",
        "Client",
        "ClientDocument",
        "ClientInquiry",
        "CompanyExpense",
        "CompanyWithdrawal",
        "Invoice",
        "InvoiceItem",
        "PendingCalendarEvent",
        "PracticeTodo",
        "Session",
        "SessionLog",
    }
)
_SCOPE_FUNCTIONS = frozenset({"scope_to_practice"})
_SCOPE_METHODS = frozenset(
    {"for_practice", "for_current_practice", "for_current_practice_with_globals"}
)
_BINDING_FIELDS = ("practice", "client", "invoice", "session")

# Unbound queries that are deliberate, each with the reason. Shrink it; never
# grow it to make a new query pass — bind the query instead.
KNOWN_UNBOUND_QUERIES = {
    # The fields dict it unpacks starts with practice=self.practice.
    "utils/bank_import.py:_classify_transaction",
    # Invoice numbers are unique across the instance, so numbering has to see
    # every practice's invoices.
    "utils/invoice_helpers.py:get_next_invoice_number",
    # Scoped by the caller's filters dict ({"practice": ...}); these should take
    # a required practice keyword like get_year_revenue does.
    "utils/revenue_helpers.py:get_total_revenue",
    "utils/revenue_helpers.py:get_revenue_stats",
    "utils/revenue_helpers.py:_status_breakdown_for_year",
    "utils/revenue_helpers.py:_status_breakdown_all_time",
    # Filtered by a client the caller already scoped, via the filters dict.
    "utils/revenue_helpers.py:get_client_revenue",
    # Cancellation-fee session ids, used only to exclude rows from the
    # practice's own sessions.
    "utils/tag_helpers.py:get_sessions_missing_log",
    # Client codes are unique across the instance; the suggestion has to avoid
    # every existing code.
    "views/client_views.py:suggest_client_code",
}


def _is_binding_keyword(name: str) -> bool:
    return (
        any(part.endswith(_BINDING_FIELDS) for part in name.split("__"))
        or name in ("pk", "id")
        or name.endswith("__in")
    )


def _unbound_queries(source: str):
    """
    Yield (lineno, function) for each Model.objects query on a practice-owned
    model that nothing binds to a practice.

    Bound means: a for_practice()/for_current_practice() call in the chain, a
    filter keyword on a practice, client, invoice or session field (or a pk /
    __in list of ids the caller already scoped), an OuterRef, being wrapped in
    scope_to_practice() — directly or via the variable it is assigned to — or
    being a Prefetch queryset, which inherits its parent's scope.
    """
    tree = ast.parse(source)
    parent = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def enclosing(node, types):
        while node in parent:
            node = parent[node]
            if isinstance(node, types):
                return node
        return None

    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Attribute)
            and node.attr == "objects"
            and isinstance(node.value, ast.Name)
            and node.value.id in PRACTICE_OWNED_MODELS
        ):
            continue
        top, bound = node, False
        while True:
            up = parent.get(top)
            if isinstance(up, ast.Attribute) and up.value is top:
                bound |= up.attr in _SCOPE_METHODS
            elif isinstance(up, ast.Call) and up.func is top:
                for inner in ast.walk(up):
                    if (
                        isinstance(inner, ast.keyword)
                        and inner.arg
                        and _is_binding_keyword(inner.arg)
                    ):
                        bound = True
                    if isinstance(inner, ast.Name) and inner.id == "OuterRef":
                        bound = True
            else:
                break
            top = up
        wrapper = parent.get(top)
        if isinstance(wrapper, ast.keyword) and wrapper.arg == "queryset":
            bound = True
        if isinstance(wrapper, ast.Call) and getattr(wrapper.func, "id", None) == "Prefetch":
            bound = True
        function = enclosing(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        call = enclosing(node, ast.Call)
        while call is not None and not bound:
            if getattr(call.func, "id", None) in _SCOPE_FUNCTIONS:
                bound = True
            call = enclosing(call, ast.Call)
        statement = enclosing(node, (ast.Assign, ast.AnnAssign))
        if not bound and statement is not None and function is not None:
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            names = {t.id for t in targets if isinstance(t, ast.Name)}
            for inner in ast.walk(function):
                if (
                    isinstance(inner, ast.Call)
                    and getattr(inner.func, "id", None) in _SCOPE_FUNCTIONS
                    and inner.args
                    and getattr(inner.args[0], "id", None) in names
                ) or (
                    isinstance(inner, ast.Attribute)
                    and inner.attr in _SCOPE_METHODS
                    and getattr(inner.value, "id", None) in names
                ):
                    bound = True
        if not bound:
            yield node.lineno, function.name if function else "<module>"


class UnboundQueryGuardrailTests(SimpleTestCase):
    """
    A helper that takes no practice cannot be caught by the fail-open patterns
    above: there is no `if practice:` to find. Both run-3 aggregate leaks
    (_get_booked_hours, PracticeDayCalculator._session_dates) were of this kind.
    """

    def test_practice_owned_queries_are_bound(self):
        offenders = []
        for rel, source in _source_files():
            if not rel.startswith(("utils/", "views/", "templatetags/")):
                continue
            for lineno, function in _unbound_queries(source):
                if f"{rel}:{function}" not in KNOWN_UNBOUND_QUERIES:
                    offenders.append(f"{rel}:{lineno} {function}")
        self.assertEqual(
            offenders,
            [],
            "Bind the query: scope_to_practice(qs, practice[, path]), for_current_practice(), "
            "or filter through a client/invoice/session that is already scoped.",
        )

    def test_allowlist_has_no_stale_entries(self):
        found = {
            f"{rel}:{function}"
            for rel, source in _source_files()
            for _, function in _unbound_queries(source)
        }
        self.assertEqual(sorted(KNOWN_UNBOUND_QUERIES - found), [])

    def test_detects_an_unbound_helper(self):
        source = (
            "def booked(start, end):\n"
            "    return Session.objects.filter(session_date__gte=start).count()\n"
        )
        self.assertEqual(list(_unbound_queries(source)), [(2, "booked")])

    def test_scope_to_practice_on_a_variable_binds(self):
        source = (
            "def booked(start, *, practice):\n"
            "    qs = Session.objects.filter(session_date__gte=start)\n"
            "    qs = scope_to_practice(qs, practice, 'client__practice')\n"
            "    return qs.count()\n"
        )
        self.assertEqual(list(_unbound_queries(source)), [])


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


class AggregatesStayInTheirPracticeTests(TestCase):
    """Counts and sums built from practice data only include the practice's own rows."""

    def setUp(self):
        self.a = Practice.objects.create(
            name="A", slug="agg-a", title="T", commute_distance_km=30, practice_weekdays=[0, 1]
        )
        self.b = Practice.objects.create(name="B", slug="agg-b", title="T")
        self.client_a = Client.objects.create(
            client_code="XX", full_name="Max Mustermann", practice=self.a
        )
        self.client_b = Client.objects.create(
            client_code="YY", full_name="Anna Schmidt", practice=self.b
        )

    def test_practice_days_ignore_other_practices_sessions(self):
        Session.objects.create(client=self.client_a, session_date=date(2026, 3, 2), duration=60)
        before = PracticeDayCalculator(self.a, 2026).calculate()
        # A Monday (a configured weekday for A) on which only B had a session.
        Session.objects.create(client=self.client_b, session_date=date(2026, 3, 9), duration=60)
        after = PracticeDayCalculator(self.a, 2026).calculate()

        self.assertEqual(after.session_days, before.session_days)
        self.assertEqual(after.deduction_total, before.deduction_total)

    def test_booked_hours_count_only_the_practice_sessions(self):
        today = date.today()
        Session.objects.create(client=self.client_b, session_date=today, duration=60)
        start = today - timedelta(days=7)

        for scope in (self.a, None):
            with self.subTest(scope=scope):
                self.assertEqual(
                    calculate_period_capacity(start, today, practice=scope)["booked_hours"], 0
                )
        self.assertEqual(
            calculate_period_capacity(start, today, practice=self.b)["booked_hours"], 1
        )

    def test_tag_counts_only_count_the_practice_clients(self):
        tag = ClientTag.objects.create(name="Warteliste", slug="warteliste")
        self.client_a.tags.add(tag)
        self.client_b.tags.add(tag)
        user = User.objects.create_user(username="tags-a", password="testpass123")
        UserPractice.objects.create(user=user, practice=self.a, is_owner=True)
        self.client.login(username="tags-a", password="testpass123")

        for url_name, key in (("tag_list", "tags"), ("client_list", "all_tags")):
            with self.subTest(page=url_name):
                response = self.client.get(reverse(url_name))
                counts = {t.slug: t.client_count for t in response.context[key]}
                self.assertEqual(counts["warteliste"], 1)

    def test_tag_counts_are_zero_without_a_practice(self):
        tag = ClientTag.objects.create(name="Warteliste", slug="warteliste")
        self.client_a.tags.add(tag)
        counts = annotate_client_counts(ClientTag.objects.filter(pk=tag.pk), practice=None)
        self.assertEqual(counts.get().client_count, 0)
        self.assertEqual(
            annotate_client_counts(ClientTag.objects.filter(pk=tag.pk), practice=ALL_PRACTICES)
            .get()
            .client_count,
            1,
        )
