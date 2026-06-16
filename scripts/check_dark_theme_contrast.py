#!/usr/bin/env python3
"""
Dark Theme Contrast Checker
Identifies CSS classes that might have dark-on-dark or light-on-light contrast issues.
"""

import re
from collections import defaultdict
from pathlib import Path

# Directories to analyze
CSS_DIR = Path(__file__).parent.parent / "app" / "static" / "css"
TEMPLATE_DIR = Path(__file__).parent.parent / "app" / "templates"

# CSS variable patterns that indicate text elements
TEXT_CLASSES = [
    "title",
    "subtitle",
    "label",
    "description",
    "text",
    "name",
    "code",
    "number",
    "content",
    "info",
]

# Color-related CSS properties
COLOR_PROPERTIES = ["color", "background", "background-color"]


def parse_css_file(filepath):
    """Parse CSS file and extract selectors with their properties."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Remove comments
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)

    # Find all CSS rules
    rules = re.findall(r"([^{}]+)\{([^{}]+)\}", content)

    selectors_props = defaultdict(dict)
    for selector, properties in rules:
        selector = selector.strip()

        # Skip media queries, keyframes, etc.
        if "@" in selector or ":" in selector and "::" not in selector and ":not" not in selector:
            continue

        # Extract color-related properties
        has_color = "color:" in properties or "color :" in properties
        has_bg = "background:" in properties or "background-color:" in properties

        # Extract variable usage
        vars_used = re.findall(r"var\(([^)]+)\)", properties)

        selectors_props[selector] = {
            "has_color": has_color,
            "has_background": has_bg,
            "variables": vars_used,
            "file": filepath.name,
        }

    return selectors_props


def find_text_classes_in_templates():
    """Find all class names used in templates."""
    classes = set()

    for template_file in TEMPLATE_DIR.rglob("*.html"):
        with open(template_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Find all class attributes
        class_matches = re.findall(r'class="([^"]+)"', content)
        for class_str in class_matches:
            # Split multiple classes
            for cls in class_str.split():
                classes.add(cls)

    return classes


def analyze_potential_issues():
    """Analyze CSS for potential dark theme contrast issues."""
    print("🔍 Analyzing CSS files for potential dark theme contrast issues...\n")

    all_selectors = {}

    # Parse all CSS files
    for css_file in CSS_DIR.rglob("*.css"):
        selectors = parse_css_file(css_file)
        all_selectors.update(selectors)

    # Also check inline styles in templates
    template_css_files = list(TEMPLATE_DIR.rglob("*.html"))
    for template_file in template_css_files:
        if "<style>" in template_file.read_text(encoding="utf-8"):
            # Extract inline CSS
            with open(template_file, "r", encoding="utf-8") as f:
                content = f.read()
                style_blocks = re.findall(r"<style>(.*?)</style>", content, re.DOTALL)
                for style_block in style_blocks:
                    rules = re.findall(r"([^{}]+)\{([^{}]+)\}", style_block)
                    for selector, properties in rules:
                        selector = selector.strip()
                        if "@" in selector:
                            continue
                        has_color = "color:" in properties
                        has_bg = "background:" in properties or "background-color:" in properties
                        vars_used = re.findall(r"var\(([^)]+)\)", properties)
                        all_selectors[selector] = {
                            "has_color": has_color,
                            "has_background": has_bg,
                            "variables": vars_used,
                            "file": f"inline:{template_file.name}",
                        }

    # Find text-related classes
    template_classes = find_text_classes_in_templates()

    # Identify potential issues
    issues = []

    for selector, props in all_selectors.items():
        # Skip if selector explicitly sets color
        if props["has_color"]:
            continue

        # Check if this looks like a text element
        is_text_element = any(keyword in selector.lower() for keyword in TEXT_CLASSES)

        # Check if it uses a background that might cause contrast issues
        has_colored_bg = props["has_background"] and any(
            var
            for var in props["variables"]
            if "bg" in var or "warning" in var or "danger" in var or "info" in var
        )

        if is_text_element or has_colored_bg:
            # This might be a problem
            selector_name = selector.split()[-1] if " " in selector else selector
            if "." in selector_name:
                class_name = selector_name.split(".")[1].split(":")[0]
                if class_name in template_classes or is_text_element:
                    issues.append(
                        {
                            "selector": selector,
                            "file": props["file"],
                            "reason": "Text element without explicit color",
                            "has_bg": has_colored_bg,
                            "variables": props["variables"],
                        }
                    )

    # Print results
    print(f"📋 Found {len(issues)} potential contrast issues:\n")

    for issue in sorted(issues, key=lambda x: x["file"]):
        print(f"⚠️  {issue['selector']}")
        print(f"   File: {issue['file']}")
        print(f"   Reason: {issue['reason']}")
        if issue["has_bg"]:
            print(f"   Background vars: {', '.join(issue['variables'])}")
        print()

    # Summary
    print("\n📊 Summary:")
    print(f"   Total CSS rules analyzed: {len(all_selectors)}")
    print(f"   Potential issues found: {len(issues)}")
    print(f"   Template classes found: {len(template_classes)}")

    # Recommendations
    print("\n💡 Recommendations:")
    print("   1. Add 'color: var(--text-primary)' to text elements")
    print("   2. Check dark theme (data-theme='dark') for each issue")
    print("   3. Pay special attention to colored backgrounds (warnings, alerts)")
    print("   4. Test with Privacy Mode enabled")


if __name__ == "__main__":
    analyze_potential_issues()
