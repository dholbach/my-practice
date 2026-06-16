"""
Test for client creation bug fix - ensure practice is assigned.
"""

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse
from my_practice.models import Client, Practice, UserPractice


class ClientPracticeAssignmentTest(TestCase):
    """Test that new clients get practice assigned automatically."""

    def setUp(self):
        """Set up test data."""
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice-assignment",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser", password="testpass123")

        # Link user to practice
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)

    def test_new_client_gets_practice_assigned(self):
        """Test that creating a new client via keyboard shortcut (c → n) assigns practice."""
        # Simulate creating a new client via POST (like keyboard shortcut c → n)
        data = {
            "client_code": "TEST",
            "full_name": "Test Client",
            "email": "test@example.com",
            "language": "de",
            "hourly_rate_60": "90.00",
            "hourly_rate_90": "130.00",
            "active": True,
        }
        response = self.client_instance.post(reverse("client_intake"), data)

        # Should redirect to client list
        self.assertEqual(response.status_code, 302, "Should redirect after successful creation")

        # Client should exist
        self.assertTrue(
            Client.objects.filter(client_code="TEST").exists(),
            "Client should be created",
        )

        # Client should have practice assigned!
        new_client = Client.objects.get(client_code="TEST")
        self.assertIsNotNone(
            new_client.practice,
            "Client must have practice assigned (Bug: practice was None)",
        )
        self.assertEqual(
            new_client.practice.id,
            self.practice.id,
            "Client should be assigned to current practice",
        )

    def test_existing_client_keeps_practice(self):
        """Test that editing an existing client doesn't change its practice."""
        # Create client with practice
        existing_client = Client.objects.create(
            client_code="EXIST",
            full_name="Existing Client",
            email="exist@example.com",
            practice=self.practice,
            hourly_rate_60=90,
            hourly_rate_90=130,
        )

        # Edit the client
        data = {
            "client_code": "EXIST",
            "full_name": "Updated Name",
            "email": "updated@example.com",
            "language": "en",
            "hourly_rate_60": "95.00",
            "hourly_rate_90": "135.00",
            "active": True,
        }
        url = reverse("client_intake") + f"?client={existing_client.pk}"
        response = self.client_instance.post(url, data)

        # Should redirect
        self.assertEqual(response.status_code, 302)

        # Practice should still be assigned
        existing_client.refresh_from_db()
        self.assertEqual(existing_client.practice.id, self.practice.id)
        self.assertEqual(existing_client.full_name, "Updated Name")
