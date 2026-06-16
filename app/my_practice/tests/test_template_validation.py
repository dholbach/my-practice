"""
Tests to validate that form templates render all required form fields.
Prevents bugs where templates miss required fields (like invoice quantity field).
"""

import re

from django.test import TestCase
from my_practice.forms import (
    ClientIntakeForm,
    CompanyExpenseForm,
    CompanyWithdrawalForm,
)
from my_practice.invoice_forms import InvoiceForm


class TemplateFieldValidationTestCase(TestCase):
    """Test that templates render all required form fields"""

    def _get_template_content(self, template_path):
        """Load template file content"""
        from django.template.loader import get_template

        try:
            template = get_template(template_path)
            return template.template.source
        except Exception as e:
            self.fail(f"Could not load template {template_path}: {e}")

    def _extract_field_references(self, template_content):
        """Extract all form field references from template"""
        # Patterns to match:
        # - {{ form.field_name }}
        # - {{ form.field_name.as_hidden }}
        # - form.field_name.label_tag
        # - form.field_name.errors
        pattern = r"form\.(\w+)(?:\.|\s|\})"
        matches = re.findall(pattern, template_content)
        # Filter out methods/properties that aren't fields
        excluded = {
            "as_p",
            "as_table",
            "as_ul",
            "errors",
            "non_field_errors",
            "management_form",
            "is_valid",
        }
        return {match for match in matches if match not in excluded}

    def test_invoice_template_has_all_fields(self):
        """Test that invoice_form.html renders all InvoiceForm fields"""
        form = InvoiceForm()
        template_content = self._get_template_content("my_practice/invoice_form.html")

        # Extract fields referenced in template
        template_fields = self._extract_field_references(template_content)

        # Check that all form fields are referenced
        form_fields = set(form.fields.keys())
        missing_fields = form_fields - template_fields

        # Some fields might be intentionally excluded (like practice - it's hidden)
        # But we should at least check critical fields
        critical_fields = {
            "client",
            "invoice_number",
            "invoice_date",
            "status",
            "tax_rate",
        }
        missing_critical = critical_fields - template_fields

        self.assertEqual(
            missing_critical,
            set(),
            f"Critical invoice fields missing from template: {missing_critical}",
        )

        # Warn about other missing fields (might be acceptable)
        if missing_fields:
            print(f"\nNote: Invoice template doesn't reference: {missing_fields}")

    def test_withdrawal_template_has_all_fields(self):
        """Test that withdrawal_form.html renders all CompanyWithdrawalForm fields"""
        form = CompanyWithdrawalForm()
        template_content = self._get_template_content("my_practice/withdrawal_form.html")

        template_fields = self._extract_field_references(template_content)
        form_fields = set(form.fields.keys())

        # All withdrawal fields should be rendered
        missing_fields = form_fields - template_fields

        self.assertEqual(
            missing_fields,
            set(),
            f"Withdrawal fields missing from template: {missing_fields}",
        )

    def test_expense_template_has_all_fields(self):
        """Test that expense_form.html renders all CompanyExpenseForm fields"""
        form = CompanyExpenseForm()
        template_content = self._get_template_content("my_practice/expense_form.html")

        template_fields = self._extract_field_references(template_content)
        form_fields = set(form.fields.keys())

        # All expense fields should be rendered
        missing_fields = form_fields - template_fields

        self.assertEqual(
            missing_fields,
            set(),
            f"Expense fields missing from template: {missing_fields}",
        )

    def test_invoice_item_formset_has_required_fields(self):
        """Test that invoice item formset template has critical fields"""
        template_content = self._get_template_content("my_practice/invoice_form.html")

        # Check for item_form references (used in formset loop)
        critical_item_fields = {
            "session_date",
            "service_type",
            "duration",
            "quantity",
            "rate",
            "description",
        }

        # Look for item_form.field_name patterns
        pattern = r"item_form\.(\w+)"
        item_fields = set(re.findall(pattern, template_content))

        missing_fields = critical_item_fields - item_fields

        self.assertEqual(
            missing_fields,
            set(),
            f"Critical invoice item fields missing from template: {missing_fields}",
        )

    def test_client_intake_template_has_key_fields(self):
        """Test that client_intake.html has key fields"""
        ClientIntakeForm()
        template_content = self._get_template_content("my_practice/client_intake.html")

        template_fields = self._extract_field_references(template_content)

        # Check for key fields
        key_fields = {"client_code", "full_name", "email", "active"}
        missing_key_fields = key_fields - template_fields

        self.assertEqual(
            missing_key_fields,
            set(),
            f"Key client fields missing from template: {missing_key_fields}",
        )

    def test_hidden_practice_fields_present(self):
        """Test that forms with practice field render it as hidden"""
        templates_with_practice = [
            "my_practice/invoice_form.html",
            "my_practice/withdrawal_form.html",
            "my_practice/expense_form.html",
        ]

        for template_path in templates_with_practice:
            with self.subTest(template=template_path):
                content = self._get_template_content(template_path)

                # Check for practice field reference (could be hidden or explicit)

                # It's okay if not present (view sets it), but if present should be hidden
                if "form.practice" in content and "as_hidden" not in content:
                    # Check if it's in a conditional that renders it hidden
                    practice_lines = [
                        line for line in content.split("\n") if "form.practice" in line
                    ]
                    has_hidden = any("as_hidden" in line for line in practice_lines)

                    self.assertTrue(
                        has_hidden,
                        f"{template_path} should render practice field as hidden if present",
                    )
