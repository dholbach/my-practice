"""
Test helper utilities and mixins for multi-practice testing.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import Practice, UserPractice

User = get_user_model()


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
