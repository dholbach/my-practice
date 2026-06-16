#!/usr/bin/env python3
"""
Batch fix test files by adding practice FK.
"""

from pathlib import Path

# Add practice import template
PRACTICE_IMPORT = ", Practice"

# Practice setup template
PRACTICE_SETUP = """
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
"""

files_to_fix = [
    "test_admin.py",
    "test_models.py",
    "test_views_client.py",
    "test_views_invoice.py",
    "test_views_withdrawal.py",
    "test_views_expense.py",
    "test_views_analytics.py",
]

for filename in files_to_fix:
    filepath = Path(__file__).parent / filename
    if not filepath.exists():
        print(f"Skip {filename} (not found)")
        continue

    content = filepath.read_text()
    original = content

    # 1. Add Practice to imports
    if "from my_practice.models import" in content or "from ..models import" in content:
        if "Practice" not in content.split("class")[0]:  # Only in import section
            # Find the import line
            for line_num, line in enumerate(content.split("\n")):
                if (
                    "from my_practice.models import" in line or "from ..models import" in line
                ) and "Practice" not in line:
                    if not line.strip().endswith(")"):
                        # Simple one-line import
                        new_line = line.rstrip() + ", Practice"
                        content = content.replace(line, new_line, 1)
                    break

    # 2. Add practice setup after first user creation
    if "self.practice = Practice.objects.create(" not in content:
        # Find setUp with user creation
        if "self.user = User.objects.create" in content:
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "self.user = User.objects.create" in line:
                    # Find end of user creation
                    indent = len(line) - len(line.lstrip())
                    j = i + 1
                    while j < len(lines) and (
                        lines[j].strip() == "" or lines[j].startswith(" " * (indent + 4))
                    ):
                        j += 1
                    # Insert practice setup
                    lines.insert(j, PRACTICE_SETUP)
                    content = "\n".join(lines)
                    break

    # 3. Add practice= to model creates
    models = ["Client", "Invoice", "ServiceType", "CompanyExpense", "CompanyWithdrawal"]
    for model in models:
        pattern = f"{model}.objects.create("
        if pattern in content:
            parts = content.split(pattern)
            new_parts = [parts[0]]
            for i, part in enumerate(parts[1:], 1):
                # Check if practice= already exists in this create call
                paren_count = 1
                end = 0
                for j, char in enumerate(part):
                    if char == "(":
                        paren_count += 1
                    elif char == ")":
                        paren_count -= 1
                        if paren_count == 0:
                            end = j
                            break

                create_block = part[: end + 1]
                if "practice=" not in create_block:
                    # Add practice before closing paren
                    new_block = (
                        part[:end] + "\n            practice=self.practice,\n        " + part[end:]
                    )
                    new_parts.append(new_block)
                else:
                    new_parts.append(part)

            content = pattern.join(new_parts)

    if content != original:
        filepath.write_text(content)
        print(f"✓ Fixed {filename}")
    else:
        print(f"- {filename} (no changes)")

print("\nDone!")
