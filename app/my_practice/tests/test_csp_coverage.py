"""Guardrails for the Content Security Policy and flash-message escaping.

script-src has no 'unsafe-inline' (config/settings.py, SECURE_CSP), so the
browser runs an inline script only if it carries the per-request nonce, and
never runs an inline event-handler attribute. Two failure modes are invisible
in review and in the test client, because only a browser enforces CSP:

1. **An inline ``<script>`` without ``nonce="{{ csp_nonce }}"``.** The page
   renders fine; the browser silently skips the script, so tabs, charts or
   form helpers just stop working.
2. **An ``onclick=``-style attribute.** Same symptom, one element at a time.
   Wire the handler with addEventListener (or an Alpine ``x-on:``) instead.

Before this test the nonce had never worked at all: the csp context processor
was missing, ``{{ csp_nonce }}`` rendered empty, and the policy fell back to
'unsafe-inline' — while base.html rendered every flash message with ``|safe``,
so a client name, a bank-CSV payer name or an exception text was inserted into
the page as raw HTML.

The checks read template source; a script tag or handler built at runtime in
JavaScript is not seen. Both lists below are ratchets: shrink, never grow.
"""

import re
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils.csp import CSP
from django.utils.html import format_html

from .test_helpers import BaseTestCase

TEMPLATE_DIR = Path(settings.BASE_DIR) / "templates"

SCRIPT_TAG = re.compile(r"<script\b([^>]*)>", re.IGNORECASE)
NONCE_ATTR = 'nonce="{{ csp_nonce }}"'
# on<event>= followed by a quote: an HTML attribute, not the word "onclick=" in
# a comment or an `el.onclick = fn` assignment in JS.
INLINE_HANDLER = re.compile(r"\son[a-z]+\s*=\s*[\"']", re.IGNORECASE)

# Inline scripts that may run without the nonce. Empty — keep it that way.
KNOWN_SCRIPTS_WITHOUT_NONCE: frozenset[str] = frozenset()
# Templates allowed to keep an inline on*= handler. Empty — keep it that way.
KNOWN_INLINE_HANDLERS: frozenset[str] = frozenset()


def _templates():
    for path in sorted(TEMPLATE_DIR.rglob("*.html")):
        yield str(path.relative_to(TEMPLATE_DIR)).replace("\\", "/"), path.read_text()


class InlineScriptNonceTests(SimpleTestCase):
    def test_every_inline_script_carries_the_nonce(self):
        offenders = []
        for name, source in _templates():
            for match in SCRIPT_TAG.finditer(source):
                attrs = match.group(1)
                if "src=" in attrs or "application/json" in attrs:
                    continue
                if NONCE_ATTR not in attrs and name not in KNOWN_SCRIPTS_WITHOUT_NONCE:
                    line = source.count("\n", 0, match.start()) + 1
                    offenders.append(f"{name}:{line}")
        self.assertEqual(
            offenders,
            [],
            f"Inline <script> without {NONCE_ATTR} — the CSP blocks it in the browser.",
        )

    def test_no_inline_event_handler_attributes(self):
        offenders = []
        for name, source in _templates():
            if name in KNOWN_INLINE_HANDLERS:
                continue
            for match in INLINE_HANDLER.finditer(source):
                line = source.count("\n", 0, match.start()) + 1
                offenders.append(f"{name}:{line}: {match.group(0).strip()}")
        self.assertEqual(
            offenders,
            [],
            "Inline on*= handlers never run under this CSP; use addEventListener or x-on:.",
        )

    def test_script_src_does_not_allow_unsafe_inline(self):
        script_src = settings.SECURE_CSP["script-src"]
        self.assertNotIn(CSP.UNSAFE_INLINE, script_src)
        self.assertIn(CSP.NONCE, script_src)

    def test_script_src_does_not_allow_unsafe_eval(self):
        # Alpine's CSP build interprets x-* expressions itself; with
        # 'unsafe-eval' back, injected markup could run arbitrary JS again.
        self.assertNotIn(CSP.UNSAFE_EVAL, settings.SECURE_CSP["script-src"])


# x-data / x-on:… / :attr / @event attribute values, per template.
ALPINE_ATTR = re.compile(r'\s(?:x-[a-z:.-]+|:[a-z-]+|@[a-z.-]+)\s*=\s*"([^"]*)"')
# What the CSP build of Alpine refuses (globals) or cannot parse (functions).
# A refused global throws when the handler runs — for `confirm(...) ||
# $event.preventDefault()` that meant the delete went ahead unconfirmed. Use
# the data-confirm / data-print / data-navigate / data-copy attributes of
# static/js/ui_actions.js, or a component registered with Alpine.data().
ALPINE_FORBIDDEN = re.compile(
    r"\b(?:window|document|navigator|localStorage|sessionStorage|location|console|"
    r"confirm|alert|prompt|setTimeout|setInterval|fetch|eval|Function|function)\b|=>"
)
# x-data="factory()" calls a global; the CSP build needs x-data="factory".
ALPINE_GLOBAL_FACTORY = re.compile(r"^\s*[A-Za-z_$][\w$]*\s*\(")


class AlpineCspBuildTests(SimpleTestCase):
    def test_base_loads_the_csp_build(self):
        base = (TEMPLATE_DIR / "base.html").read_text()
        self.assertIn("js/alpine-csp.min.js", base)
        self.assertNotIn("js/alpine.min.js", base)

    def test_alpine_expressions_avoid_globals_and_functions(self):
        offenders = []
        for name, source in _templates():
            for match in ALPINE_ATTR.finditer(source):
                expression = re.sub(r"\{%.*?%\}|\{\{.*?\}\}|'[^']*'", "", match.group(1))
                if ALPINE_FORBIDDEN.search(expression) or (
                    match.group(0).lstrip().startswith("x-data")
                    and ALPINE_GLOBAL_FACTORY.match(expression)
                ):
                    offenders.append(f"{name}: {match.group(0).strip()[:100]}")
        self.assertEqual(offenders, [])


class NoHtmxTests(SimpleTestCase):
    def test_no_template_relies_on_htmx_attributes(self):
        # htmx was removed for static/js/partial_post.js (data-post); an hx-*
        # attribute left behind would do nothing, silently.
        offenders = [
            f"{name}: {match.group(0)}"
            for name, source in _templates()
            for match in re.finditer(r"\shx-[a-z-]+=", source)
        ]
        self.assertEqual(offenders, [])


class NonceRenderedTests(BaseTestCase):
    def test_page_nonce_matches_the_policy_header(self):
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(reverse("dashboard"))

        header = response.headers["Content-Security-Policy"]
        header_nonce = re.search(r"'nonce-([^']+)'", header).group(1)
        page_nonces = set(re.findall(r'<script nonce="([^"]*)"', response.content.decode()))
        self.assertTrue(page_nonces, "base.html renders at least one inline script")
        self.assertEqual(page_nonces, {header_nonce})

    def test_policy_forbids_framing(self):
        """X_FRAME_OPTIONS is only set with DEBUG off; frame-ancestors covers
        every configuration, including a dev server reachable on the LAN."""
        self.client.login(username="testuser", password="testpass123")
        header = self.client.get(reverse("dashboard")).headers["Content-Security-Policy"]
        self.assertIn("frame-ancestors 'none'", header)


class FlashMessageEscapingTests(TestCase):
    def _render_with(self, *texts):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        request.current_practice = None
        request.session = {}
        request._messages = FallbackStorage(request)
        for text in texts:
            messages.info(request, text)
        return render_to_string(
            "base.html", {"messages": messages.get_messages(request)}, request=request
        )

    def test_plain_message_is_escaped(self):
        # e.g. a payer name from a bank CSV, or an exception text.
        html = self._render_with("Alias '<img src=x onerror=alert(1)>' saved.")
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html)

    def test_format_html_message_keeps_its_markup(self):
        # The email views build their success message with format_html.
        html = self._render_with(
            format_html('Sent to <span class="sensitive-data">{}</span>', "<b>x</b>")
        )
        self.assertIn('<span class="sensitive-data">&lt;b&gt;x&lt;/b&gt;</span>', html)
