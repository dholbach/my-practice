"""
Tests for aggregation helper functions.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from my_practice.models import CompanyExpense, CompanyWithdrawal, Practice
from my_practice.utils.aggregation_helpers import (
    get_category_breakdown,
    get_grand_total,
    get_monthly_breakdown,
    get_year_over_year_comparison,
    get_yearly_totals,
)


class AggregationHelpersTestCase(TestCase):
    """Test cases for aggregation helper functions."""

    def setUp(self):
        """Create test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="aggregation_helpers-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Create expenses across different years
        CompanyExpense.objects.create(
            date=date(2024, 1, 15),
            description="Rent 2024",
            amount=Decimal("1000.00"),
            category="rent",
            is_tax_deductible=True,
            practice=self.practice,
        )
        CompanyExpense.objects.create(
            date=date(2024, 6, 15),
            description="Software 2024",
            amount=Decimal("500.00"),
            category="software",
            is_tax_deductible=True,
            practice=self.practice,
        )
        CompanyExpense.objects.create(
            date=date(2025, 1, 15),
            description="Rent 2025",
            amount=Decimal("1200.00"),
            category="rent",
            is_tax_deductible=True,
            practice=self.practice,
        )
        CompanyExpense.objects.create(
            date=date(2025, 2, 15),
            description="Office 2025",
            amount=Decimal("300.00"),
            category="office",
            is_tax_deductible=False,
            practice=self.practice,
        )

        # Create withdrawals
        CompanyWithdrawal.objects.create(
            date=date(2025, 1, 10),
            description="Withdrawal 1",
            amount=Decimal("2000.00"),
            practice=self.practice,
        )
        CompanyWithdrawal.objects.create(
            date=date(2025, 3, 10),
            description="Withdrawal 2",
            amount=Decimal("3000.00"),
            practice=self.practice,
        )

    def test_get_yearly_totals(self):
        """Test yearly totals aggregation."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        yearly = get_yearly_totals(CompanyExpense.objects.all())
        yearly_list = list(yearly)

        self.assertEqual(len(yearly_list), 2)
        # Check 2025 (desc order, should be first)
        self.assertEqual(yearly_list[0]["date__year"], 2025)
        self.assertEqual(yearly_list[0]["total"], Decimal("1500.00"))
        # Check 2024
        self.assertEqual(yearly_list[1]["date__year"], 2024)
        self.assertEqual(yearly_list[1]["total"], Decimal("1500.00"))

    def test_get_yearly_totals_ascending(self):
        """Test yearly totals with ascending order."""
        yearly = get_yearly_totals(CompanyExpense.objects.all(), order="asc")
        yearly_list = list(yearly)

        self.assertEqual(yearly_list[0]["date__year"], 2024)
        self.assertEqual(yearly_list[1]["date__year"], 2025)

    def test_get_category_breakdown(self):
        """Test category breakdown aggregation."""
        categories = get_category_breakdown(
            CompanyExpense.objects.all(),
            category_choices=dict(CompanyExpense.CATEGORY_CHOICES),
        )

        self.assertEqual(len(categories), 3)  # rent, software, office

        # Check rent (highest total)
        self.assertEqual(categories[0]["category"], "rent")
        self.assertEqual(categories[0]["total"], Decimal("2200.00"))
        self.assertEqual(categories[0]["count"], 2)
        self.assertIn("category_name", categories[0])

    def test_get_category_breakdown_without_choices(self):
        """Test category breakdown without human-readable names."""
        categories = get_category_breakdown(CompanyExpense.objects.all())
        categories_list = list(categories)

        self.assertEqual(len(categories_list), 3)
        # Should not have category_name when choices not provided
        self.assertNotIn("category_name", categories_list[0])

    def test_get_monthly_breakdown(self):
        """Test monthly breakdown for a specific year."""
        monthly = get_monthly_breakdown(CompanyWithdrawal.objects.all(), 2025)

        self.assertEqual(len(monthly), 2)  # Jan and Mar
        self.assertEqual(monthly["2025-01"], Decimal("2000.00"))
        self.assertEqual(monthly["2025-03"], Decimal("3000.00"))
        self.assertNotIn("2025-02", monthly)  # No data for Feb

    def test_get_grand_total(self):
        """Test grand total calculation."""
        total = get_grand_total(CompanyExpense.objects.all())
        self.assertEqual(total, Decimal("3000.00"))

    def test_get_grand_total_with_filter(self):
        """Test grand total with filter condition."""
        from django.db.models import Q

        tax_deductible = get_grand_total(
            CompanyExpense.objects.all(), filter_condition=Q(is_tax_deductible=True)
        )
        self.assertEqual(tax_deductible, Decimal("2700.00"))  # 1000 + 500 + 1200

    def test_get_grand_total_empty(self):
        """Test grand total on empty queryset."""
        CompanyExpense.objects.all().delete()
        total = get_grand_total(CompanyExpense.objects.all())
        self.assertEqual(total, Decimal("0"))

    def test_get_year_over_year_comparison(self):
        """Test year-over-year comparison."""
        comparison = get_year_over_year_comparison(CompanyExpense.objects.all(), [2024, 2025])

        self.assertEqual(len(comparison), 2)
        self.assertEqual(comparison[2024]["total"], Decimal("1500.00"))
        self.assertIsNone(comparison[2024]["growth"])  # First year has no growth
        self.assertEqual(comparison[2025]["total"], Decimal("1500.00"))
        self.assertEqual(comparison[2025]["growth"], 0.0)  # Same as previous year

    def test_custom_field_names(self):
        """Test aggregation with custom field names."""
        yearly = get_yearly_totals(
            CompanyWithdrawal.objects.all(), date_field="date", amount_field="amount"
        )
        yearly_list = list(yearly)

        self.assertEqual(len(yearly_list), 1)
        self.assertEqual(yearly_list[0]["total"], Decimal("5000.00"))
