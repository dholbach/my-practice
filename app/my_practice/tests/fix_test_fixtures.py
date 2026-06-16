#!/usr/bin/env python3
"""
Fix test fixtures by adding practice FK to all model creations.

This script automatically adds practice FK to:
- Client.objects.create()
- Invoice.objects.create()
- ServiceType.objects.create()
- CompanyExpense.objects.create()
- CompanyWithdrawal.objects.create()
- GoogleCalendarToken.objects.create()
"""

import re
from pathlib import Path


def add_practice_import(content):
    """Add Practice to imports if not present."""
    # Check if Practice is already imported
    if "from ..models import" in content and "Practice" not in content:
        # Find the import line
        import_pattern = r"(from \.\.models import [^)]+)"
        match = re.search(import_pattern, content)
        if match:
            import_line = match.group(1)
            if "Practice" not in import_line:
                # Add Practice to imports
                new_import = import_line.rstrip() + ", Practice"
                content = content.replace(import_line, new_import)
    return content


def add_practice_to_setup(content):
    """Add practice creation to setUp methods if not present."""
    # Check if practice is already created
    if "self.practice = Practice.objects.create(" in content:
        return content

    # Find setUp methods
    setup_pattern = r"(    def setUp\(self\):.*?)(        self\.user = User\.objects\.create_user)"
    match = re.search(setup_pattern, content, re.DOTALL)

    if match:
        setup_start = match.group(1)
        user_creation = match.group(2)

        # Add practice creation after user creation
        practice_code = """
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

"""
        new_content = setup_start + user_creation + practice_code
        content = content.replace(match.group(0), new_content)

    return content


def add_practice_fk(content):
    """Add practice FK to model creations."""
    models_to_fix = [
        "Client.objects.create(",
        "Invoice.objects.create(",
        "ServiceType.objects.create(",
        "CompanyExpense.objects.create(",
        "CompanyWithdrawal.objects.create(",
        "GoogleCalendarToken.objects.create(",
    ]

    for model_create in models_to_fix:
        # Find all occurrences
        pattern = rf"({re.escape(model_create)}[^)]+\))"
        matches = re.finditer(pattern, content, re.DOTALL)

        for match in matches:
            creation_block = match.group(1)
            # Check if practice FK is already present
            if "practice=" not in creation_block:
                # Add practice FK before closing parenthesis
                new_block = (
                    creation_block.rstrip(")") + ",\n            practice=self.practice,\n        )"
                )
                content = content.replace(creation_block, new_block)

    return content


def fix_test_file(file_path):
    """Fix a single test file."""
    print(f"Processing {file_path}...")

    with open(file_path, "r") as f:
        content = f.read()

    original_content = content

    # Skip files that already have practice setup
    if "self.practice = Practice.objects.create(" in content:
        print("  Skipped (already has practice)")
        return False

    # Apply fixes
    content = add_practice_import(content)
    content = add_practice_to_setup(content)
    content = add_practice_fk(content)

    if content != original_content:
        with open(file_path, "w") as f:
            f.write(content)
        print("  Fixed!")
        return True
    else:
        print("  No changes needed")
        return False


def main():
    """Fix all test files."""
    test_dir = Path(__file__).parent
    fixed_count = 0

    # Get all test files
    test_files = list(test_dir.glob("test_*.py"))

    print(f"Found {len(test_files)} test files\n")

    for test_file in test_files:
        # Skip already fixed files
        if test_file.name in [
            "test_views_invoice_simple.py",
            "test_views_tax.py",
            "test_helpers.py",
            "test_multi_practice.py",
        ]:
            continue

        if fix_test_file(test_file):
            fixed_count += 1

    print(f"\n✓ Fixed {fixed_count} test files")


if __name__ == "__main__":
    main()
