"""Markdown rendering template filter for clinical notes (P-009)."""

import markdown as md
import nh3
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "code",
    "pre",
    "hr",
    "a",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
}

_ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
}


@register.filter(name="render_markdown", is_safe=True)
def render_markdown(value: str) -> str:
    """Render a markdown string to sanitized HTML."""
    if not value:
        return ""
    html = md.markdown(
        value,
        extensions=["nl2br", "sane_lists", "fenced_code"],
    )
    return mark_safe(nh3.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRIBUTES))
