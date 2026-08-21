"""Tests for Django admin configuration."""

from datetime import date
from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase

from my_practice.admin import (
    BankTransactionAdmin,
    ChecklistItemPauseAdmin,
    ClientAdmin,
    ClientAliasAdmin,
    ClientInquiryAdmin,
    ClientNoteAdmin,
    ClientProfileAdmin,
    ClientTagAdmin,
    CompanyExpenseAdmin,
    CompanyWithdrawalAdmin,
    ExpenseCategoryRuleAdmin,
    GebuhZifferAdmin,
    InvoiceAdmin,
    InvoiceItemAdmin,
    InvoiceItemAdminForm,
    LeistungserfassungAdmin,
    MarketingPeriodAdmin,
    OperationalChecklistCompletionAdmin,
    PendingCalendarEventAdmin,
    PracticeAdmin,
    PracticeTodoAdmin,
    ServiceTypeAdmin,
    SessionAdmin,
    SessionLogAdmin,
    SupervisionItemAdmin,
    TimeOffAdmin,
)
from my_practice.models import (
    BankTransaction,
    ChecklistItemPause,
    Client,
    ClientAlias,
    ClientInquiry,
    ClientNote,
    ClientProfile,
    ClientTag,
    CompanyExpense,
    CompanyWithdrawal,
    ExpenseCategoryRule,
    GebuhZiffer,
    Invoice,
    InvoiceItem,
    Leistungserfassung,
    MarketingPeriod,
    OperationalChecklistCompletion,
    PendingCalendarEvent,
    Practice,
    PracticeTodo,
    ServiceType,
    Session,
    SessionLog,
    SupervisionItem,
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


class RemainingAdminConfigTestCase(TestCase):
    """Configuration smoke tests for the admin classes not covered above.

    Mirrors AdminConfigTestCase's pattern: instantiate AdminClass(Model, site)
    and check list_display/list_filter — catches typos/renames in field names
    without needing DB fixtures.
    """

    def setUp(self):
        self.site = AdminSite()

    def test_client_alias_admin_registered(self):
        admin_instance = ClientAliasAdmin(ClientAlias, self.site)
        self.assertIn("alias_name", admin_instance.list_display)
        self.assertIn("client_link", admin_instance.list_display)
        self.assertIn("client", admin_instance.list_filter)

    def test_client_inquiry_admin_registered(self):
        admin_instance = ClientInquiryAdmin(ClientInquiry, self.site)
        self.assertIn("full_name", admin_instance.list_display)
        self.assertIn("status", admin_instance.list_display)
        self.assertIn("status", admin_instance.list_filter)

    def test_marketing_period_admin_registered(self):
        admin_instance = MarketingPeriodAdmin(MarketingPeriod, self.site)
        self.assertIn("description", admin_instance.list_display)
        self.assertIn("is_active_badge", admin_instance.list_display)

    def test_pending_calendar_event_admin_registered(self):
        admin_instance = PendingCalendarEventAdmin(PendingCalendarEvent, self.site)
        self.assertIn("status", admin_instance.list_display)
        self.assertIn("status", admin_instance.list_filter)
        self.assertIn("mark_pending", admin_instance.actions)
        self.assertIn("mark_skipped", admin_instance.actions)

    def test_expense_category_rule_admin_registered(self):
        admin_instance = ExpenseCategoryRuleAdmin(ExpenseCategoryRule, self.site)
        self.assertIn("match_key", admin_instance.list_display)
        self.assertIn("category", admin_instance.list_filter)

    def test_client_profile_admin_registered(self):
        admin_instance = ClientProfileAdmin(ClientProfile, self.site)
        self.assertIn("client", admin_instance.list_display)
        self.assertIn("arbeitsdiagnose_preview", admin_instance.list_display)

    def test_session_log_admin_registered(self):
        admin_instance = SessionLogAdmin(SessionLog, self.site)
        self.assertIn("session", admin_instance.list_display)
        self.assertIn("session_type", admin_instance.list_filter)

    def test_supervision_item_admin_registered(self):
        admin_instance = SupervisionItemAdmin(SupervisionItem, self.site)
        self.assertIn("client", admin_instance.list_display)
        self.assertIn("status", admin_instance.list_display)

    def test_client_note_admin_registered(self):
        admin_instance = ClientNoteAdmin(ClientNote, self.site)
        self.assertIn("client", admin_instance.list_display)
        self.assertIn("note_date", admin_instance.list_display)

    def test_invoice_item_admin_registered(self):
        admin_instance = InvoiceItemAdmin(InvoiceItem, self.site)
        self.assertIn("invoice", admin_instance.list_display)
        self.assertIn("service_type", admin_instance.list_display)
        self.assertEqual(admin_instance.form, InvoiceItemAdminForm)

    def test_practice_todo_admin_registered(self):
        admin_instance = PracticeTodoAdmin(PracticeTodo, self.site)
        self.assertIn("title_display", admin_instance.list_display)
        self.assertIn("mark_completed", admin_instance.actions)
        self.assertIn("mark_incomplete", admin_instance.actions)
        self.assertIn("set_high_priority", admin_instance.actions)

    def test_client_tag_admin_registered(self):
        admin_instance = ClientTagAdmin(ClientTag, self.site)
        self.assertIn("name", admin_instance.list_display)
        self.assertIn("category_badge", admin_instance.list_display)
        self.assertIn("is_system", admin_instance.list_filter)

    def test_bank_transaction_admin_registered(self):
        admin_instance = BankTransactionAdmin(BankTransaction, self.site)
        self.assertIn("transaction_date", admin_instance.list_display)
        self.assertIn("matched_invoice_link", admin_instance.list_display)
        self.assertIn("match_confidence", admin_instance.list_filter)

    def test_session_admin_registered(self):
        admin_instance = SessionAdmin(Session, self.site)
        self.assertIn("client", admin_instance.list_display)
        self.assertIn("has_log", admin_instance.list_display)
        self.assertIn("has_invoice_item", admin_instance.list_display)

    def test_gebuh_ziffer_admin_registered(self):
        admin_instance = GebuhZifferAdmin(GebuhZiffer, self.site)
        self.assertIn("nummer", admin_instance.list_display)
        self.assertIn("sort_order", admin_instance.list_editable)

    def test_leistungserfassung_admin_registered(self):
        admin_instance = LeistungserfassungAdmin(Leistungserfassung, self.site)
        self.assertIn("session", admin_instance.list_display)
        self.assertIn("ziffer", admin_instance.list_display)

    def test_operational_checklist_completion_admin_registered(self):
        admin_instance = OperationalChecklistCompletionAdmin(
            OperationalChecklistCompletion, self.site
        )
        self.assertIn("checklist_type", admin_instance.list_display)
        self.assertIn("year_month", admin_instance.list_display)

    def test_checklist_item_pause_admin_registered(self):
        admin_instance = ChecklistItemPauseAdmin(ChecklistItemPause, self.site)
        self.assertIn("checklist_type", admin_instance.list_display)
        self.assertIn("is_active", admin_instance.list_display)


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


class InvoiceItemAdminFormTests(TestCase):
    """InvoiceItem.session became blank=True (P-122), so the admin form must
    enforce "session XOR description" itself — otherwise a blank row only
    fails inside InvoiceItem.save(), producing an unhandled 500 instead of a
    normal form error (used by both InvoiceItemInline and InvoiceItemAdmin)."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="admin-invoiceitem-form",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.service_type = ServiceType.objects.create(
            code="individual", name="60 Min Session", practice=self.practice
        )
        self.client_obj = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        self.invoice = Invoice.objects.create(
            client=self.client_obj,
            invoice_number="TC-1",
            invoice_date=date.today(),
            status=Invoice.Status.DRAFT,
            practice=self.practice,
        )

    def test_neither_session_nor_description_is_invalid(self):
        form = InvoiceItemAdminForm(
            data={
                "invoice": str(self.invoice.pk),
                "service_type": str(self.service_type.pk),
                "rate": "90.00",
                "quantity": "1.00",
                "group_size": "1",
                "total": "90.00",
                "description": "",
            }
        )
        self.assertFalse(form.is_valid())

    def test_both_session_and_description_is_invalid(self):
        session = Session.objects.create(
            client=self.client_obj, session_date=date.today(), duration=60
        )
        form = InvoiceItemAdminForm(
            data={
                "invoice": str(self.invoice.pk),
                "session": str(session.pk),
                "service_type": str(self.service_type.pk),
                "rate": "90.00",
                "quantity": "1.00",
                "group_size": "1",
                "total": "90.00",
                "description": "Consulting",
            }
        )
        self.assertFalse(form.is_valid())

    def test_description_only_is_valid(self):
        self.practice.allows_free_form_items = True
        self.practice.save()
        form = InvoiceItemAdminForm(
            data={
                "invoice": str(self.invoice.pk),
                "service_type": str(self.service_type.pk),
                "rate": "800.00",
                "quantity": "1.00",
                "group_size": "1",
                "total": "800.00",
                "description": "Consulting",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
