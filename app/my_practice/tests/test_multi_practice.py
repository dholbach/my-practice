"""
Tests for multi-practice functionality.
"""

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase

from ..models import (
    Client,
    CompanyExpense,
    CompanyWithdrawal,
    GoogleCalendarToken,
    Invoice,
    Practice,
    ServiceType,
    UserPractice,
)


class PracticeModelTest(TestCase):
    """Test Practice model"""

    def setUp(self):
        """Create test practice"""
        self.practice, _ = Practice.objects.get_or_create(
            slug="test",
            defaults={
                "name": "Test Practice",
                "is_active": True,
            },
        )

    def test_practice_creation(self):
        """Test creating a practice"""
        self.assertEqual(self.practice.name, "Test Practice")
        self.assertEqual(self.practice.slug, "test")
        self.assertTrue(self.practice.is_active)

    def test_practice_str(self):
        """Test practice string representation"""
        expected = f"{self.practice.name} - {self.practice.title}"
        self.assertEqual(str(self.practice), expected)

    def test_slug_auto_generation(self):
        """Test slug is auto-generated from name if not set"""
        practice = Practice.objects.create(name="My Coaching Business")
        self.assertEqual(practice.slug, "my-coaching-business")

    def test_slug_uniqueness(self):
        """Test slug must be unique"""
        with self.assertRaises(IntegrityError):
            Practice.objects.create(name="Another Practice", slug="test")


class UserPracticeModelTest(TestCase):
    """Test UserPractice M2M model"""

    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(username="testuser", password="test123")
        self.practice, _ = Practice.objects.get_or_create(
            slug="test", defaults={"name": "Test Practice"}
        )

    def test_user_practice_creation(self):
        """Test creating UserPractice relationship"""
        up = UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.assertEqual(up.user, self.user)
        self.assertEqual(up.practice, self.practice)
        self.assertTrue(up.is_owner)

    def test_user_practice_str(self):
        """Test UserPractice string representation"""
        up = UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        expected = f"{self.user.username} → {self.practice.name} (Eigentümer)"
        self.assertEqual(str(up), expected)

    def test_user_practice_unique_together(self):
        """Test user-practice combination must be unique"""
        UserPractice.objects.create(user=self.user, practice=self.practice)
        with self.assertRaises(IntegrityError):
            UserPractice.objects.create(user=self.user, practice=self.practice)

    def test_many_to_many_relationship(self):
        """Test M2M relationship between users and practices"""
        UserPractice.objects.create(user=self.user, practice=self.practice)

        # Access via user.practices
        self.assertIn(self.practice, self.user.practices.all())

        # Access via practice.users
        self.assertIn(self.user, self.practice.users.all())

    def test_multiple_practices_per_user(self):
        """Test one user can have access to multiple practices"""
        # First practice relationship (from setUp)
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)

        # Second practice
        practice2 = Practice.objects.create(name="Coaching", slug="coaching")
        UserPractice.objects.create(user=self.user, practice=practice2, is_owner=False)

        self.assertEqual(self.user.practices.count(), 2)


class PracticeScopedModelsTest(TestCase):
    """Test practice FKs on all scoped models"""

    def setUp(self):
        """Create test practices"""
        # Create two practices for comparison
        self.practice1 = Practice.objects.create(
            name="Therapy Practice",
            slug="multi_practice-therapy",
            title="Test Practitioner",
            email="therapy@practice.com",
            city="Berlin",
        )

        self.practice2 = Practice.objects.create(
            name="Coaching Practice",
            slug="multi_practice-coaching",
            email="coaching@practice.com",
            city="Munich",
        )

    def test_client_practice_scoping(self):
        """Test clients are scoped to practice"""
        client1 = Client.objects.create(
            practice=self.practice1,
            client_code="CL1",
            full_name="Client One",
            email="client1@test.com",
        )
        client2 = Client.objects.create(
            practice=self.practice2,
            client_code="CL2",
            full_name="Client Two",
            email="client2@test.com",
        )

        # Practice 1 has only client1
        self.assertEqual(self.practice1.clients.count(), 1)
        self.assertIn(client1, self.practice1.clients.all())
        self.assertNotIn(client2, self.practice1.clients.all())

        # Practice 2 has only client2
        self.assertEqual(self.practice2.clients.count(), 1)
        self.assertIn(client2, self.practice2.clients.all())
        self.assertNotIn(client1, self.practice2.clients.all())

    def test_invoice_practice_scoping(self):
        """Test invoices are scoped to practice"""
        client1 = Client.objects.create(
            practice=self.practice1,
            client_code="CL1",
            full_name="Client One",
            email="client1@test.com",
        )

        Invoice.objects.create(
            practice=self.practice1,
            client=client1,
            invoice_number="TEST-1",
        )

        self.assertEqual(self.practice1.invoices.count(), 1)
        self.assertEqual(self.practice2.invoices.count(), 0)

    def test_expense_practice_scoping(self):
        """Test expenses are scoped to practice"""
        from datetime import date

        CompanyExpense.objects.create(
            practice=self.practice1,
            date=date.today(),
            amount=100.00,
            description="Test expense 1",
        )

        self.assertEqual(self.practice1.expenses.count(), 1)
        self.assertEqual(self.practice2.expenses.count(), 0)

    def test_withdrawal_practice_scoping(self):
        """Test withdrawals are scoped to practice"""
        from datetime import date

        CompanyWithdrawal.objects.create(
            practice=self.practice1,
            date=date.today(),
            amount=500.00,
        )

        self.assertEqual(self.practice1.withdrawals.count(), 1)
        self.assertEqual(self.practice2.withdrawals.count(), 0)

    def test_service_type_practice_scoping(self):
        """Test service types are scoped to practice"""
        ServiceType.objects.create(
            practice=self.practice1,
            code="therapy_60",
            name="60-Min Therapy",
        )

        self.assertEqual(self.practice1.service_types.count(), 1)
        self.assertEqual(self.practice2.service_types.count(), 0)

    def test_calendar_token_practice_scoping(self):
        """Test calendar tokens are scoped to practice"""
        from django.utils import timezone

        GoogleCalendarToken.objects.create(
            practice=self.practice1,
            token="test_token",
            client_id="test_client",
            client_secret="test_secret",
            expires_at=timezone.now(),
        )

        self.assertEqual(self.practice1.calendar_tokens.count(), 1)
        self.assertEqual(self.practice2.calendar_tokens.count(), 0)


class MultiPracticeWorkflowTest(TestCase):
    """Test multi-practice workflows"""

    def setUp(self):
        """Create complete multi-practice setup"""
        # Create two practices
        self.therapy = Practice.objects.create(
            name="Therapy Practice",
            slug="multi_practice-therapy-workflow",
            title="Therapist",
            email="therapy@practice.com",
            city="Berlin",
        )

        self.coaching = Practice.objects.create(
            name="Coaching Practice",
            slug="multi_practice-coaching-workflow",
            title="Coach",
            email="coaching@practice.com",
            city="Munich",
        )

        # Create user
        self.user = User.objects.create_user(username="practitioner", password="test123")

        # Assign user to both practices
        UserPractice.objects.create(user=self.user, practice=self.therapy, is_owner=True)
        UserPractice.objects.create(user=self.user, practice=self.coaching, is_owner=False)

    def test_user_has_access_to_multiple_practices(self):
        """Test user can access both practices"""
        self.assertEqual(self.user.practices.count(), 2)
        self.assertIn(self.therapy, self.user.practices.all())
        self.assertIn(self.coaching, self.user.practices.all())

    def test_data_separation_between_practices(self):
        """Test data is properly separated between practices"""
        # Create clients in each practice
        therapy_client = Client.objects.create(
            practice=self.therapy,
            client_code="TC1",
            full_name="Therapy Client",
            email="therapy@test.com",
        )
        coaching_client = Client.objects.create(
            practice=self.coaching,
            client_code="CC1",
            full_name="Coaching Client",
            email="coaching@test.com",
        )

        # Therapy practice should only see therapy client
        self.assertEqual(self.therapy.clients.count(), 1)
        self.assertEqual(self.therapy.clients.first(), therapy_client)

        # Coaching practice should only see coaching client
        self.assertEqual(self.coaching.clients.count(), 1)
        self.assertEqual(self.coaching.clients.first(), coaching_client)

    def test_ownership_tracking(self):
        """Test ownership is tracked per practice"""
        therapy_up = UserPractice.objects.get(user=self.user, practice=self.therapy)
        coaching_up = UserPractice.objects.get(user=self.user, practice=self.coaching)

        self.assertTrue(therapy_up.is_owner)
        self.assertFalse(coaching_up.is_owner)
