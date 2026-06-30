"""
Custom template tags and filters for the payments app.
"""

import html as _html

from django import template
from django.utils.safestring import mark_safe

from ..utils.chart_helpers import GERMAN_MONTHS_SHORT

register = template.Library()


@register.filter(name="currency")
def currency(value, symbol="€"):
    """
    Format a number as currency with German/EU format.
    Uses period as thousands separator and comma as decimal separator.
    Usage: {{ value|currency }} or {{ value|currency:'$' }}
    Example: 11064.03 -> "11.064,03 €"
    """
    if value is None:
        return "–"

    try:
        value = float(value)
        # Format with 2 decimal places and thousands separator
        formatted = f"{value:,.2f}"
        # Convert to German format: swap . and , then replace , with .
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{formatted}\u00a0{symbol}"
    except ValueError, TypeError:
        return value


@register.filter(name="currency_rounded")
def currency_rounded(value, symbol="€"):
    """
    Format a number as currency with German/EU format, rounded to full euros.
    Usage: {{ value|currency_rounded }} or {{ value|currency_rounded:'$' }}
    Example: 11064.57 -> "11.065 €"
    """
    if value is None:
        return "–"

    try:
        value = float(value)
        # Round to nearest integer
        rounded = round(value)
        # Format with thousands separator
        formatted = f"{rounded:,}"
        # Convert to German format: replace , with .
        formatted = formatted.replace(",", ".")
        return f"{formatted}\u00a0{symbol}"
    except ValueError, TypeError:
        return value


@register.filter(name="percent")
def percent(value, decimals=1):
    """
    Format a number as percentage.
    Usage: {{ value|percent }} or {{ value|percent:2 }}
    """
    if value is None:
        return "–"

    try:
        value = float(value)
        return f"{value:.{decimals}f}%"
    except ValueError, TypeError:
        return value


@register.filter(name="percentage")
def percentage(part, total):
    """
    Calculate percentage of part from total.
    Usage: {{ value|percentage:total }}
    """
    if part is None or total is None:
        return "–"

    try:
        part = float(part)
        total = float(total)
        if total == 0:
            return "0%"
        percentage = (part / total) * 100
        return f"{percentage:.1f}%"
    except ValueError, TypeError, ZeroDivisionError:
        return "–"


@register.filter(name="hours")
def hours(value):
    """
    Format hours with 'h' suffix.
    Usage: {{ value|hours }}
    """
    if value is None:
        return "–"

    try:
        value = float(value)
        return f"{value:.1f}h"
    except ValueError, TypeError:
        return value


@register.filter(name="js_number")
def js_number(value, default=0):
    """
    Format a number for JavaScript (always uses dot as decimal separator).
    Safe for embedding in <script> tags regardless of Django locale settings.
    Usage: {{ value|js_number }} or {{ value|js_number:0 }}
    Example: 90,00 -> 90.00
    """
    if value is None:
        return str(default)

    try:
        # Convert to float and format with dot decimal separator
        return f"{float(value):.2f}"
    except ValueError, TypeError:
        return str(default)


@register.simple_tag
def stat_card(label, value, suffix="", color="primary"):
    """
    Render a stat card component.
    Usage: {% stat_card label="Revenue" value=1234.56 suffix="€" color="success" %}
    """
    color_classes = {
        "primary": "background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);",
        "success": "background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);",
        "warning": "background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);",
        "danger": "background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);",
    }

    style = color_classes.get(color, color_classes["primary"])

    return f"""
    <div class="stat-card" style="{style}">
        <div class="stat-value">{value}{suffix}</div>
        <div class="stat-label">{label}</div>
    </div>
    """


@register.filter(name="highlight_diff")
def highlight_diff(value, threshold=0):
    """
    Add color class based on whether value is positive or negative.
    Usage: <span class="{{ value|highlight_diff }}">{{ value }}</span>
    """
    try:
        value = float(value)
        if value > threshold:
            return "text-success"
        elif value < threshold:
            return "text-danger"
        return ""
    except ValueError, TypeError:
        return ""


@register.simple_tag(takes_context=True)
def query_string(context, **kwargs):
    """
    Build query string preserving existing parameters.

    Usage:
        {% query_string page=2 %}  -> preserves all current params, sets page=2
        {% query_string status='paid' year='' %}  -> sets status, removes year
    """
    request = context.get("request")
    if not request:
        return ""

    # Start with current GET parameters
    params = request.GET.copy()

    # Update with provided kwargs
    for key, value in kwargs.items():
        if value == "" or value is None:
            # Remove parameter if value is empty
            params.pop(key, None)
        else:
            # Remove existing value first to avoid duplicates
            params.pop(key, None)
            params[key] = value

    # Build query string
    if params:
        return "&" + params.urlencode()
    return ""


@register.filter(name="format_month_year")
def format_month_year(date_value):
    """
    Format date as German month and year (e.g., "Jan 2025").
    Usage: {{ date|format_month_year }}
    """
    if date_value is None:
        return "–"

    try:
        month_name = GERMAN_MONTHS_SHORT[date_value.month - 1]
        return f"{month_name} {date_value.year}"
    except AttributeError, IndexError, ValueError, TypeError:
        return "–"


@register.filter(name="dict_get")
def dict_get(dictionary, key):
    """
    Get value from dictionary by key.
    Usage: {{ my_dict|dict_get:key_variable }}
    """
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)


@register.filter(name="abs_value")
def abs_value(value):
    """
    Return absolute value of a number.
    Usage: {{ number|abs_value }}
    """
    if value is None:
        return None
    try:
        return abs(float(value))
    except ValueError, TypeError:
        return 0


_WEEKDAY_NAMES = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


@register.filter(name="weekday_name")
def weekday_name(value):
    """
    Convert a weekday integer (0=Mon … 6=Sun) to a short German name.
    Usage: {{ 0|weekday_name }} → 'Mo'
    """
    try:
        return _WEEKDAY_NAMES[int(value)]
    except ValueError, TypeError, IndexError:
        return str(value)


@register.filter(name="privacy_name")
def privacy_name(value):
    """
    Render a name so initials are always visible and the rest is blurred in privacy mode.

    Each word becomes: first_char + <span class="sensitive-data pn-rest">remainder</span>.
    In normal mode the full name reads naturally; in privacy mode (body.privacy-mode)
    .sensitive-data gets blurred, leaving only the initials legible.

    Usage: {{ inquiry.full_name|privacy_name }}
    Output must be used with |safe or autoescape off is not needed — mark_safe is applied.
    """
    if not value:
        return ""
    parts = []
    for word in str(value).strip().split():
        if len(word) > 1:
            parts.append(
                f"{_html.escape(word[0])}"
                f'<span class="sensitive-data pn-rest">{_html.escape(word[1:])}</span>'
            )
        else:
            parts.append(_html.escape(word))
    return mark_safe(" ".join(parts))
