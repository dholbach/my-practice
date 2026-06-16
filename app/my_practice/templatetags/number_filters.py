"""
Custom template filters for number formatting
"""

from django import template

register = template.Library()


@register.filter
def format_hours(value):
    """Format hours: show integer if whole number, otherwise 1 decimal"""
    try:
        num = float(value)
        if num == int(num):
            return str(int(num))
        return f"{num:.1f}".replace(",", ".")
    except ValueError, TypeError:
        return value
