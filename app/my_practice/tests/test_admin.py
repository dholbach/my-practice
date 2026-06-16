"""Tests for Django admin configuration."""

from datetime import date

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from my_practice.admin import (
    ClientAdmin,
    CompanyExpenseAdmin,
    CompanyWithdrawalAdmin,
    InvoiceAdmin,
    PracticeAdmin,
    ServiceTypeAdmin,
    TimeOffAdmin,
)
from my_practice.models import (
    Client,
    CompanyExpense,
    CompanyWithdrawal,
    Invoice,
    Practice,
    ServiceType,
    TimeOff,
)


class MockRequest:
    """Mock request object for admin tests"""

    pass


class AdminConfigTestCase(TestCase):
    """Tests for admin configuration"""

    def setUp(self):
        """Create admin site and test user"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="admin-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.site = AdminSite()
        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="testpass123"
        )

    def test_practice_admin_registered(self):
        """Test PracticeAdmin configuration"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        admin_instance = PracticeAdmin(Practice, self.site)
        # Check fieldsets instead of list_display
        self.assertIsNotNone(admin_instance.fieldsets)
        self.assertTrue(admin_instance.readonly_fields)

    def test_client_admin_registered(self):
        """Test ClientAdmin configuration"""
        admin_instance = ClientAdmin(Client, self.site)
        self.assertIn("client_code", admin_instance.list_display)
        self.assertIn("full_name", admin_instance.list_display)
        self.assertIn("active_status", admin_instance.list_display)
        self.assertIn("active", admin_instance.list_filter)

    def test_service_type_admin_registered(self):
        """Test ServiceTypeAdmin configuration"""
        admin_instance = ServiceTypeAdmin(ServiceType, self.site)
        self.assertIn("code", admin_instance.list_display)
        self.assertIn("name", admin_instance.list_display)

    def test_invoice_admin_registered(self):
        """Test InvoiceAdmin configuration"""
        admin_instance = InvoiceAdmin(Invoice, self.site)
        self.assertIn("invoice_number", admin_instance.list_display)
        self.assertIn("client", admin_instance.list_display)
        self.assertIn("status", admin_instance.list_display)
        self.assertIn("status", admin_instance.list_filter)

    def test_company_withdrawal_admin_registered(self):
        """Test CompanyWithdrawalAdmin configuration"""
        admin_instance = CompanyWithdrawalAdmin(CompanyWithdrawal, self.site)
        self.assertIn("date", admin_instance.list_display)
        self.assertIn("amount", admin_instance.list_display)

    def test_company_expense_admin_registered(self):
        """Test CompanyExpenseAdmin configuration"""
        admin_instance = CompanyExpenseAdmin(CompanyExpense, self.site)
        self.assertIn("date", admin_instance.list_display)
        self.assertIn("category_display", admin_instance.list_display)
        self.assertIn("amount_display", admin_instance.list_display)

    def test_timeoff_admin_registered(self):
        """Test TimeOffAdmin configuration"""
        admin_instance = TimeOffAdmin(TimeOff, self.site)
        self.assertIn("title", admin_instance.list_display)
        self.assertIn("start_date", admin_instance.list_display)
        self.assertIn("end_date", admin_instance.list_display)


class AdminDisplayMethodsTestCase(TestCase):
    """Tests for custom admin display methods"""

    def setUp(self):
        """Create test data"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="admin-2",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.site = AdminSite()
        self.client_obj = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            practice=self.practice,
        )
        self.service_type = ServiceType.objects.create(
            code="therapy_60",
            name="60-Min Session",
            default_duration=60,
            practice=self.practice,
        )

    def test_invoice_admin_client_name_display(self):
        """Test that invoice admin shows client name"""
        Invoice.objects.create(
            client=self.client_obj,
            invoice_number="TC-1",
            invoice_date=date.today(),
            status="draft",
            practice=self.practice,
        )

        admin_instance = InvoiceAdmin(Invoice, self.site)
        # Check that client is in list_display
        self.assertIn("client", admin_instance.list_display)


class AdminIntegrationTestCase(TestCase):
    """Integration tests for admin interface"""

    def setUp(self):
        """Create test user and client"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="admin-3",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="testpass123"
        )
        self.test_client = TestClient()
        self.test_client.login(username="admin", password="testpass123")

    def test_admin_index_loads(self):
        """Test that admin index page loads"""
        response = self.test_client.get("/admin/")
        self.assertEqual(response.status_code, 200)

    def test_client_admin_list_loads(self):
        """Test that client admin list loads"""
        response = self.test_client.get("/admin/my_practice/client/")
        self.assertEqual(response.status_code, 200)

    def test_invoice_admin_list_loads(self):
        """Test that invoice admin list loads"""
        response = self.test_client.get("/admin/my_practice/invoice/")
        self.assertEqual(response.status_code, 200)

    def test_service_type_admin_list_loads(self):
        """Test that service type admin list loads"""
        response = self.test_client.get("/admin/my_practice/servicetype/")
        self.assertEqual(response.status_code, 200)

    def test_admin_add_client_form_loads(self):
        """Test that add client form loads"""
        response = self.test_client.get("/admin/my_practice/client/add/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "client_code")
        self.assertContains(response, "full_name")

    def test_admin_can_create_client(self):
        """Test creating client through admin"""
        data = {
            "client_code": "TC",
            "full_name": "Test Client",
            "email": "test@example.com",
            "language": "de",
            "hourly_rate_60": "90.00",
            "hourly_rate_90": "130.00",
            "cancellation_fee": "0.00",
            "active": True,
            "practice": self.practice.pk,
            # ClientDocumentInline management form (prefix is the related_name "documents")
            "documents-TOTAL_FORMS": "0",
            "documents-INITIAL_FORMS": "0",
            "documents-MIN_NUM_FORMS": "0",
            "documents-MAX_NUM_FORMS": "1000",
        }
        response = self.test_client.post("/admin/my_practice/client/add/", data)
        # 302 redirect on success
        if response.status_code == 200 and hasattr(response, "context") and response.context:
            adminform = response.context.get("adminform")
            if adminform:
                print("FORM ERRORS:", adminform.form.errors)
            inline_admin_formsets = response.context.get("inline_admin_formsets", [])
            for fs in inline_admin_formsets:
                if hasattr(fs, "formset") and fs.formset.errors:
                    print("INLINE ERRORS:", fs.formset.errors)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Client.objects.count(), 1)
        client = Client.objects.first()
        self.assertEqual(client.client_code, "TC")
