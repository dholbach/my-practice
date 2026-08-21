"""
Test helper utilities and mixins for multi-practice testing.
"""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ..models import Practice, UserPractice

User = get_user_model()


class QueryCountMixin:
    """Assert that a page's query count does not grow with the number of rows.

    The older query-count tests in this suite assert a fixed ceiling against a
    fixed amount of seed data, which is a weak guard: the dashboard test seeds
    five clients and allows eleven queries of headroom, so a freshly introduced
    N+1 adds about five queries and passes. Ceilings also drift — every one has
    a comment explaining why it was raised.

    Measuring the same page twice with different row counts tests the shape of
    the query behaviour instead of its size. O(1) stays O(1) whatever the
    baseline, so the assertion neither drifts with unrelated changes nor needs
    a magic number.
    """

    def assertQueryCountStable(self, fetch, add_rows, tolerance=0, label="page"):
        """Render twice — before and after adding rows — and compare counts.

        Args:
            fetch: callable returning the response (asserted 200 both times)
            add_rows: callable that creates more of whatever the page lists
            tolerance: extra queries allowed, for genuinely constant additions
                such as a pagination COUNT appearing once a page fills up
            label: name used in the failure message
        """
        with CaptureQueriesContext(connection) as before:
            self.assertEqual(fetch().status_code, 200, f"{label} did not render")
        baseline = len(before.captured_queries)

        add_rows()

        with CaptureQueriesContext(connection) as after:
            self.assertEqual(fetch().status_code, 200, f"{label} did not render after seeding")
        grown = len(after.captured_queries)

        growth = grown - baseline
        if growth > tolerance:
            extra = [q["sql"] for q in after.captured_queries[baseline:]][:5]
            listing = "\n    ".join(extra)
            self.fail(
                f"{label} query count grew with the row count "
                f"({baseline} -> {grown}, +{growth}, tolerance {tolerance}) — "
                f"this is what an N+1 looks like.\n  First extra queries:\n    {listing}"
            )


def link_user_to_practice(user, practice, is_owner=True):
    """
    Link a user to a practice via UserPractice.

    Uses get_or_create to avoid duplicate key errors when running tests repeatedly.
    This is required for middleware to set request.current_practice.

    Args:
        user: User instance
        practice: Practice instance
        is_owner: Whether user is owner of the practice

    Returns:
        UserPractice instance
    """
    user_practice, created = UserPractice.objects.get_or_create(
        user=user,
        practice=practice,
        defaults={"is_owner": is_owner},
    )
    return user_practice


class PracticeTestMixin:
    """
    Mixin to provide a default practice for tests.

    Usage:
        class MyTest(PracticeTestMixin, TestCase):
            def setUp(self):
                super().setUp()  # Creates self.practice
                # ... rest of setup
    """

    def setUp(self):
        """Create a default practice for testing."""
        super().setUp()

        # Create default practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="helpers-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Link user to practice if user exists (after this setUp completes)
        # Subclasses should call link_user_to_practice() after creating their user


class BaseTestCase(PracticeTestMixin, TestCase):
    """
    Base test case with practice support and user linking.

    Automatically creates:
    - A default practice (self.practice)
    - A default user (self.user)
    - UserPractice link between them

    Usage:
        class MyTest(BaseTestCase):
            def setUp(self):
                super().setUp()  # Creates practice, user, and links them
                # ... rest of setup
    """

    def setUp(self):
        """Create practice and user with proper linking."""
        super().setUp()

        # Create default user
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            email="testuser@example.com",
        )

        # Link user to practice for middleware
        link_user_to_practice(self.user, self.practice, is_owner=True)

    pass


def create_test_practice(name="Test Practice", slug=None):
    """
    Create a test practice with default values.

    Args:
        name: Practice name
        slug: URL slug (auto-generated from name if not provided)

    Returns:
        Practice instance
    """
    return Practice.objects.create(
        name=name,
        slug=slug or name.lower().replace(" ", "-"),
        title="Test Practitioner",
        email=f"{slug or 'test'}@practice.com",
        city="Berlin",
        is_active=True,
    )
