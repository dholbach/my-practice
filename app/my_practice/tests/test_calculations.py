"""
Tests for calculation utilities.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from my_practice.models import Client, Invoice, InvoiceItem, Practice, ServiceType, Session
from my_practice.utils import count_sessions, count_sessions_rounded


class _MockSession:
    """Minimal Session stand-in for MockItem."""

    def __init__(self, duration):
        self.duration = duration


class _MockServiceType:
    """Minimal ServiceType stand-in for MockItem."""

    def __init__(self, code="therapy_60"):
        self.code = code


class MockItem:
    """Mock item for testing without database."""

    def __init__(self, duration, quantity=1, service_type=None, group_size=1):
        self.session_id = True  # truthy — session is set
        self.session = _MockSession(duration)
        self.quantity = Decimal(str(quantity))
        self.service_type = service_type or _MockServiceType()
        self.group_size = group_size


class CountSessionsTest(TestCase):
    """Tests for count_sessions function."""

    def test_single_60min_session(self):
        """Test counting a single 60-minute session."""
        items = [MockItem(duration=60, quantity=1)]
        result = count_sessions(items)
        self.assertEqual(result, 1.0)

    def test_single_90min_session(self):
        """Test counting a single 90-minute session."""
        items = [MockItem(duration=90, quantity=1)]
        result = count_sessions(items)
        self.assertEqual(result, 1.5)

    def test_single_15min_session(self):
        """Test counting a single 15-minute check-in."""
        items = [MockItem(duration=15, quantity=1)]
        result = count_sessions(items)
        self.assertEqual(result, 0.25)

    def test_mixed_durations(self):
        """Test counting mixed session durations."""
        items = [
            MockItem(duration=60, quantity=1),  # 1.0
            MockItem(duration=90, quantity=1),  # 1.5
            MockItem(duration=15, quantity=1),  # 0.25
        ]
        result = count_sessions(items)
        self.assertEqual(result, 2.75)

    def test_quantity_multiplier_60min(self):
        """Test that quantity multiplies session count for 60min."""
        items = [MockItem(duration=60, quantity=3)]
        result = count_sessions(items)
        self.assertEqual(result, 3.0)

    def test_quantity_multiplier_90min(self):
        """Test that quantity multiplies session count for 90min."""
        items = [MockItem(duration=90, quantity=2)]
        result = count_sessions(items)
        self.assertEqual(result, 3.0)  # 2 * 1.5 = 3.0

    def test_fractional_quantity(self):
        """Test fractional quantity values."""
        items = [MockItem(duration=60, quantity=0.5)]
        result = count_sessions(items)
        self.assertEqual(result, 0.5)

    def test_exclude_cancellations(self):
        """Test that Ausfall items are excluded by default."""
        items = [
            MockItem(duration=60, quantity=1),
            MockItem(duration=60, quantity=1, service_type=_MockServiceType("cancel_fee")),
            MockItem(duration=90, quantity=1),
        ]
        result = count_sessions(items, exclude_cancellations=True)
        self.assertEqual(result, 2.5)  # 1.0 + 1.5

    def test_include_cancellations(self):
        """Test that Ausfall items can be included."""
        items = [
            MockItem(duration=60, quantity=1),
            MockItem(duration=60, quantity=1, service_type=_MockServiceType("cancel_fee")),
            MockItem(duration=90, quantity=1),
        ]
        result = count_sessions(items, exclude_cancellations=False)
        self.assertEqual(result, 3.5)  # 1.0 + 1.0 + 1.5

    def test_empty_list(self):
        """Test counting empty list."""
        result = count_sessions([])
        self.assertEqual(result, 0.0)

    def test_zero_quantity(self):
        """Test items with zero quantity."""
        items = [
            MockItem(duration=60, quantity=1),
            MockItem(duration=60, quantity=0),
        ]
        result = count_sessions(items)
        self.assertEqual(result, 1.0)


class CountSessionsRoundedTest(TestCase):
    """Tests for count_sessions_rounded function."""

    def test_rounds_up(self):
        """Test rounding up (>= 0.5)."""
        items = [
            MockItem(duration=60, quantity=1),  # 1.0
            MockItem(duration=90, quantity=2),  # 3.0
        ]
        result = count_sessions_rounded(items)
        self.assertEqual(result, 4)  # 4.0 exact

    def test_rounds_down(self):
        """Test rounding down (< 0.5)."""
        items = [
            MockItem(duration=60, quantity=1),  # 1.0
            MockItem(duration=15, quantity=1),  # 0.25
        ]
        result = count_sessions_rounded(items)
        self.assertEqual(result, 1)  # 1.25 rounds to 1

    def test_exact_integer(self):
        """Test exact integer values."""
        items = [
            MockItem(duration=60, quantity=3),  # 3.0
        ]
        result = count_sessions_rounded(items)
        self.assertEqual(result, 3)


class CountSessionsTherapistHoursTest(TestCase):
    """Tests for count_sessions() with therapist_hours=True."""

    def test_individual_session_unchanged(self):
        """Individual sessions (group_size=1) are unaffected by therapist_hours."""
        items = [MockItem(duration=60, quantity=1, group_size=1)]
        self.assertEqual(
            count_sessions(items, therapist_hours=True),
            count_sessions(items, therapist_hours=False),
        )

    def test_group_session_divides_by_group_size(self):
        """Each participant's item contributes therapist_duration / group_size."""
        # One item for one participant in a group of 8, 2h session.
        # That item represents 1/8 of the therapist's time.
        items = [MockItem(duration=120, quantity=1, group_size=8)]
        result = count_sessions(items, therapist_hours=True)
        self.assertAlmostEqual(result, 0.25)  # 2h / 8 = 0.25h per participant

    def test_group_session_all_participants_sum_to_therapist_time(self):
        """Summing all 8 participants gives the actual therapist hours worked."""
        # 8 identical items (one per client), each with group_size=8
        items = [MockItem(duration=120, quantity=1, group_size=8)] * 8
        result = count_sessions(items, therapist_hours=True)
        self.assertAlmostEqual(result, 2.0)  # 8 × (2h / 8) = 2h

    def test_group_session_billing_unchanged(self):
        """Without therapist_hours, group sessions show full billing hours per client."""
        items = [MockItem(duration=120, quantity=1, group_size=8)]
        result = count_sessions(items, therapist_hours=False)
        self.assertAlmostEqual(result, 2.0)  # 120min / 60 = 2h (per client)

    def test_mixed_individual_and_group(self):
        """Mix of individual and group sessions sums correctly."""
        items = [
            MockItem(duration=60, quantity=1, group_size=1),  # 1h individual
            MockItem(duration=120, quantity=1, group_size=8),  # 2h group (÷8 = 0.25h)
        ]
        result = count_sessions(items, therapist_hours=True)
        # 1.0 + (2.0 / 8) = 1.0 + 0.25 = 1.25
        self.assertAlmostEqual(result, 1.25)

    def test_therapist_hours_excludes_cancellations(self):
        """Cancellations are still excluded when therapist_hours=True."""
        items = [
            MockItem(duration=60, quantity=1, group_size=4),
            MockItem(
                duration=60, quantity=1, service_type=_MockServiceType("cancel_fee"), group_size=4
            ),
        ]
        result = count_sessions(items, therapist_hours=True)
        self.assertAlmostEqual(result, 0.25)  # 1h / 4, cancellation skipped

    def test_missing_group_size_attribute_defaults_to_one(self):
        """Items without a group_size attribute behave like individual sessions."""
        item = MockItem(duration=60, quantity=1)
        del item.group_size  # Simulate a plain object without the attribute
        result = count_sessions([item], therapist_hours=True)
        self.assertAlmostEqual(result, 1.0)


class RealWorldScenariosTest(TestCase):
    """Tests for real-world usage scenarios."""

    def test_typical_month_mixed_sessions(self):
        """Test a typical month with mixed session types."""
        items = [
            MockItem(duration=60, quantity=1),  # Regular session
            MockItem(duration=60, quantity=1),  # Regular session
            MockItem(duration=90, quantity=1),  # Extended session
            MockItem(
                duration=60, quantity=1, service_type=_MockServiceType("cancel_fee")
            ),  # Cancellation
        ]
        result = count_sessions_rounded(items)
        self.assertEqual(result, 4)  # 1 + 1 + 1.5 = 3.5, rounds to 4

    def test_mixed_durations_month_example(self):
        """Test a month mixing 60- and 90-minute sessions."""
        items = [
            MockItem(duration=60, quantity=1),  # therapy_60
            MockItem(duration=60, quantity=1),  # therapy_60
            MockItem(duration=90, quantity=1),  # therapy_90
            MockItem(duration=60, quantity=1),  # therapy_60
            MockItem(duration=90, quantity=1),  # therapy_90
        ]
        result = count_sessions_rounded(items)
        self.assertEqual(result, 6)  # 3*1.0 + 2*1.5 = 6.0

    def test_only_checkins(self):
        """Test month with only 15-minute check-ins."""
        items = [
            MockItem(duration=15, quantity=1),
            MockItem(duration=15, quantity=1),
            MockItem(duration=15, quantity=1),
            MockItem(duration=15, quantity=1),
        ]
        result = count_sessions(items)
        self.assertEqual(result, 1.0)  # 4 * 0.25 = 1.0

    def test_group_sessions(self):
        """Test group sessions (typically 60 or 90 minutes)."""
        items = [
            MockItem(duration=60, quantity=1),
            MockItem(duration=90, quantity=1),
        ]
        result = count_sessions_rounded(items)
        self.assertEqual(result, 2)  # 1.0 + 1.5 = 2.5, banker's rounding to 2


class DatabaseIntegrationTest(TestCase):
    """Integration tests with actual database models."""

    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="calculations-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.client = Client.objects.create(
            client_code="TEST",
            full_name="Test Client",
            email="test@example.com",
            hourly_rate_60=Decimal("90.00"),
            hourly_rate_90=Decimal("130.00"),
            practice=self.practice,
        )

        self.service_60 = ServiceType.objects.create(
            code="individual",
            name_en="Individual Session",
            name_de="Einzelsitzung",
            practice=self.practice,
        )

        self.service_90 = ServiceType.objects.create(
            code="double",
            name_en="Extended Session",
            name_de="Doppelsitzung",
            practice=self.practice,
        )

        self.service_cancel = ServiceType.objects.create(
            code="cancel_fee",
            name_en="Cancellation Fee",
            name_de="Ausfallhonorar",
            practice=self.practice,
        )

        self.invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-1",
            invoice_date=date(2024, 1, 15),
            status="paid",
            practice=self.practice,
        )

    def test_database_items_60min(self):
        """Test counting with real database items (60min)."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        s1 = Session.objects.create(client=self.client, session_date=date(2024, 1, 5), duration=60)
        s2 = Session.objects.create(client=self.client, session_date=date(2024, 1, 12), duration=60)
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_60,
            session=s1,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )

        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_60,
            session=s2,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )

        items = self.invoice.items.select_related("session").all()
        result = count_sessions_rounded(items)
        self.assertEqual(result, 2)

    def test_database_items_mixed(self):
        """Test counting with mixed duration items from database."""
        s1 = Session.objects.create(client=self.client, session_date=date(2024, 1, 5), duration=60)
        s2 = Session.objects.create(client=self.client, session_date=date(2024, 1, 12), duration=90)
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_60,
            session=s1,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )

        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_90,
            session=s2,
            rate=Decimal("130.00"),
            quantity=Decimal("1.00"),
        )

        items = self.invoice.items.select_related("session").all()
        result = count_sessions(items)
        self.assertEqual(result, 2.5)

        result_rounded = count_sessions_rounded(items)
        self.assertEqual(result_rounded, 2)  # 2.5 uses banker's rounding

    def test_database_with_cancellation(self):
        """Test that cancellation-fee items are excluded."""
        s1 = Session.objects.create(client=self.client, session_date=date(2024, 1, 5), duration=60)
        s2 = Session.objects.create(client=self.client, session_date=date(2024, 1, 12), duration=60)
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_60,
            session=s1,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )

        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_cancel,
            session=s2,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )

        items = self.invoice.items.select_related("session").all()
        result = count_sessions_rounded(items)
        self.assertEqual(result, 1)  # Only non-Ausfall counted

    def test_database_with_quantity_greater_than_one(self):
        """Test database items with quantity > 1."""
        s1 = Session.objects.create(client=self.client, session_date=date(2024, 1, 5), duration=60)
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_60,
            session=s1,
            rate=Decimal("90.00"),
            quantity=Decimal("3.00"),  # 3 sessions in one item
        )

        items = self.invoice.items.select_related("session").all()
        result = count_sessions_rounded(items)
        self.assertEqual(result, 3)


class EdgeCasesTest(TestCase):
    """Tests for edge cases and boundary conditions."""

    def test_very_long_session(self):
        """Test very long session (e.g., 120 minutes)."""
        items = [MockItem(duration=120, quantity=1)]
        result = count_sessions(items)
        self.assertEqual(result, 2.0)

    def test_very_short_session(self):
        """Test very short session (e.g., 5 minutes)."""
        items = [MockItem(duration=5, quantity=1)]
        result = count_sessions(items)
        self.assertAlmostEqual(result, 0.083333, places=5)

    def test_multiple_cancellations(self):
        """Test multiple cancellations in a row."""
        items = [
            MockItem(duration=60, quantity=1, service_type=_MockServiceType("cancel_fee")),
            MockItem(duration=60, quantity=1, service_type=_MockServiceType("cancel_fee")),
            MockItem(duration=60, quantity=1, service_type=_MockServiceType("cancel_fee")),
        ]
        result = count_sessions_rounded(items)
        self.assertEqual(result, 0)

    def test_partial_cancel_code_excluded(self):
        """Service types whose code contains 'cancel' anywhere are excluded."""
        items = [
            MockItem(duration=60, quantity=1),
            MockItem(
                duration=60, quantity=1, service_type=_MockServiceType("cancel_session_50pct")
            ),
        ]
        result = count_sessions_rounded(items)
        self.assertEqual(result, 1)

    def test_large_quantity(self):
        """Test with large quantity values."""
        items = [MockItem(duration=60, quantity=100)]
        result = count_sessions(items)
        self.assertEqual(result, 100.0)
