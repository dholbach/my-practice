"""Guardrail for privacy mode: personal data must be blurred, and only personal data.

This is a ratchet in the style of ``test_i18n_coverage.py`` and
``test_css_tokens.py``. It exists because the same bug class has now been fixed
one site at a time three separate times, in both directions:

* **under-blur** — a name rendered in the clear (#321 restored a missing
  ``sensitive-data`` class; the command palette shipped search results
  unblurred, fixed in #424);
* **over-blur** — ``sensitive-data`` wrapped around something that was never
  personal in the first place, hiding a form label or a client code that *is*
  the privacy-safe representation (#426).

Both are invisible in review and in normal use: nothing renders differently
unless privacy mode happens to be switched on. ``CODEBASE_STANDARDS.md`` has
carried "client.full_name without sensitive-data class?" as a manual quarterly
checklist line since P-038 — this turns that grep into CI.

The two checks are deliberately asymmetric, because the two mistakes look
different in the source:

* a personal field rendered outside any ``.sensitive-data`` element is
  under-blur;
* a ``.sensitive-data`` element containing no personal field at all is
  over-blur — blur applied to something with nothing to hide. Matching on the
  *absence* of PII rather than on known-safe tokens like ``client_code`` is
  what catches ``invoice_form.html``'s ``<div class="form-group
  sensitive-data">`` around a ``{{ form.client }}`` select, where the leaked
  text came from ``Client.__str__`` and no giveaway token appeared in the
  template at all.

Shrink ``KNOWN_UNPROTECTED``; never grow it to make a new render pass.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

TEMPLATES_DIR = Path(settings.BASE_DIR) / "templates"

# Model fields (and the query annotations aliasing them) that identify a person
# or carry their contact/clinical details. `payer_name` is the counterparty on a
# bank transaction — a client where the money came in, a supplier where it went
# out. `client_name` is the annotated alias used by the analytics queries.
PII_FIELDS = (
    "full_name",
    "client_name",
    "date_of_birth",
    "email",
    "phone",
    "address",
    "cost_carrier",
    "arbeitsdiagnose",
    "payer_name",
)
PII_RE = re.compile(r"\b([\w.]+)\.(" + "|".join(PII_FIELDS) + r")\b")

# Roots whose fields are the practice's own details, not a client's: the
# therapist's contact data is on their invoices and their website. `form` covers
# every widget/label/error render — an input the therapist is typing into is
# never blurred anywhere in the app, and blurring one hides its label too (#426).
NON_PERSONAL_ROOTS = frozenset({"form", "practice", "request"})

# PDF templates render a document, not the app UI. Privacy mode is a
# shoulder-surfing toggle on screen; an invoice or a treatment contract has to
# carry the client's real name and address to be valid at all.
EXEMPT_TEMPLATES = frozenset(
    {
        "my_practice/invoice_pdf_de.html",
        "my_practice/invoice_pdf_en.html",
        "my_practice/treatment_contract_pdf.html",
        "my_practice/intake_form_pdf.html",
        "my_practice/questionnaire_pdf.html",
    }
)

# Renders that are deliberately not blurred, keyed by template. Each entry is a
# decision, not a backlog item — add one only with a reason that holds up, and
# only for the specific expression.
KNOWN_UNPROTECTED: dict[str, frozenset[str]] = {
    # Negative transactions only (see BankExpenseReviewView/withdrawal review
    # querysets): the counterparty is a supplier, landlord or the practice's own
    # account, never a client. Client payments are inbound and live on
    # bank_review.html, where payer_name *is* blurred.
    "my_practice/bank_expense_review.html": frozenset({"trans.payer_name"}),
    "my_practice/bank_withdrawal_review.html": frozenset({"trans.payer_name"}),
    "my_practice/expense_form.html": frozenset({"tx.payer_name"}),
    # Passed to fetch() to pre-load client-code suggestions; never inserted into
    # the page, so there is no rendered text for a blur to cover.
    "my_practice/inquiry_convert_confirm.html": frozenset({"script:inquiry.full_name"}),
    # `object` here is the Practice being deleted — the therapist's own address.
    "my_practice/practice_confirm_delete.html": frozenset({"object.email"}),
}

# Attributes whose value the browser renders as visible or announced text, so a
# personal field in one leaks the same way body text does. Every other attribute
# (href, value, data-*) is out of scope by construction: privacy mode blurs
# painted text, and a mailto: target or an <input value> is neither.
VISIBLE_ATTRS = frozenset({"title", "alt", "aria-label", "placeholder"})

VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }
)
TAG_RE = re.compile(r"<(/?)([a-zA-Z][\w-]*)((?:[^<>\"']|\"[^\"]*\"|'[^']*')*)>")
COMMENT_RE = re.compile(r"{%\s*comment\s*%}.*?{%\s*endcomment\s*%}|{#.*?#}|<!--.*?-->", re.DOTALL)
# The sites that actually put a value on the page.
OUTPUT_RE = re.compile(r"{{.*?}}", re.DOTALL)
# A {% blocktrans with client_email=client.email %} binds the field to a local
# alias and renders it as {{ client_email }} inside the block body. Both halves
# have to be resolved: the binding names the field but renders nothing, and the
# alias renders but doesn't look personal — which is how
# client_gdpr_delete_confirm.html leaked an email address past a plain grep.
BLOCKTRANS_RE = re.compile(
    r"{%\s*blocktrans(?:late)?\b(?P<args>[^%]*)%}(?P<body>.*?){%\s*endblocktrans(?:late)?\s*%}",
    re.DOTALL,
)
BINDING_RE = re.compile(r"\b(\w+)\s*=\s*([\w.]+)")
VARIABLE_RE = re.compile(r"{{\s*([\w.]+)")
ATTR_RE = re.compile(r"([\w-]+)\s*=\s*[\"'][^\"']*$")
SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)


def _blank_preserving_lines(match):
    """Replace a match with spaces, keeping newlines so offsets map to lines."""
    return "".join(char if char == "\n" else " " for char in match.group(0))


def _all_templates():
    for path in sorted(TEMPLATES_DIR.rglob("*.html")):
        rel_name = str(path.relative_to(TEMPLATES_DIR)).replace("\\", "/")
        if rel_name not in EXEMPT_TEMPLATES:
            yield path, rel_name


def _alias_bindings(text):
    """Return [(body_start, body_end, {alias: expression})] per blocktrans block."""
    blocks = []
    for match in BLOCKTRANS_RE.finditer(text):
        bindings = {
            alias: expression
            for alias, expression in BINDING_RE.findall(match.group("args"))
            if PII_RE.fullmatch(expression)
        }
        if bindings:
            blocks.append((match.start("body"), match.end("body"), bindings))
    return blocks


def _rendered_expression(chunk, position, blocks):
    """The expression a {{ }} site puts on the page, with blocktrans aliases resolved."""
    match = PII_RE.search(chunk)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    variable = VARIABLE_RE.match(chunk)
    if variable:
        for begin, end, bindings in blocks:
            if begin <= position < end and variable.group(1) in bindings:
                return bindings[variable.group(1)]
    return None


def _blurred_spans(text):
    """Return (start, end) offsets of every element carrying `sensitive-data`.

    Tracks nesting with a tag stack rather than matching a class against a
    single line: the class sits on a wrapper in most templates
    (`<td class="sensitive-data">`, `<div class="value sensitive-data">`), so a
    per-line check would miss everything it covers.
    """
    stack, depth, spans, opened_at = [], 0, [], None
    for match in TAG_RE.finditer(text):
        closing, name, attrs = match.group(1), match.group(2).lower(), match.group(3)
        if closing:
            while stack:
                open_name, was_blurred = stack.pop()
                if was_blurred:
                    depth -= 1
                    if depth == 0:
                        spans.append((opened_at, match.end()))
                if open_name == name:
                    break
            continue
        if name in VOID_ELEMENTS or attrs.rstrip().endswith("/"):
            continue
        blurred = "sensitive-data" in attrs
        if blurred:
            if depth == 0:
                opened_at = match.start()
            depth += 1
        stack.append((name, blurred))
    return spans


def _enclosing_attribute(text, position):
    """Name of the HTML attribute `position` sits inside, or None for body text."""
    tag_start = text.rfind("<", 0, position)
    if tag_start == -1 or text.rfind(">", tag_start, position) != -1:
        return None
    attr_match = ATTR_RE.search(text[tag_start:position])
    return attr_match.group(1).lower() if attr_match else None


def _scan(path):
    """Yield (line_number, expression) for every personal field rendered unblurred.

    Hits inside a <script> block carry a `script:` prefix. They are reported
    rather than skipped — JS that writes a name into the DOM leaks exactly like
    body text does, which is how the command palette shipped unblurred search
    results (#424) — but they are a different question from a `{{ }}` in the
    markup ("what does the JS do with this?" rather than "wrap it"), and the
    prefix keeps an allowlist entry for one from silencing the other.
    """
    raw = path.read_text(encoding="utf-8")
    text = COMMENT_RE.sub(_blank_preserving_lines, raw)
    spans = _blurred_spans(text)
    blocks = _alias_bindings(text)
    scripts = [(m.start(), m.end()) for m in SCRIPT_RE.finditer(text)]
    for output in OUTPUT_RE.finditer(text):
        start, chunk = output.start(), output.group(0)
        if "privacy_name" in chunk:
            continue
        if any(begin <= start < end for begin, end in spans):
            continue
        attribute = _enclosing_attribute(text, start)
        if attribute is not None and attribute not in VISIBLE_ATTRS:
            continue
        expression = _rendered_expression(chunk, start, blocks)
        if expression is None or expression.split(".")[0] in NON_PERSONAL_ROOTS:
            continue
        prefix = "script:" if any(begin <= start < end for begin, end in scripts) else ""
        yield text.count("\n", 0, start) + 1, f"{prefix}{expression}"


class PrivacyModeCoverageTests(SimpleTestCase):
    """Personal data is blurred in privacy mode; nothing else is."""

    def test_personal_data_is_privacy_wrapped(self):
        violations = []
        for path, rel_name in _all_templates():
            allowed = KNOWN_UNPROTECTED.get(rel_name, frozenset())
            for line_no, expression in _scan(path):
                if expression not in allowed:
                    violations.append(f"{rel_name}:{line_no} renders {{{{ {expression} }}}}")
        self.assertEqual(
            violations,
            [],
            "Personal data rendered outside a '.sensitive-data' element — wrap "
            "it, apply the |privacy_name filter, or add it to "
            f"KNOWN_UNPROTECTED with a reason: {violations}",
        )

    def test_privacy_blur_covers_only_personal_data(self):
        """A `.sensitive-data` element with no personal field inside it is
        over-blur: it hides a label, a client code or a form control that was
        already safe to show (#426)."""
        violations = []
        for path, rel_name in _all_templates():
            text = COMMENT_RE.sub(_blank_preserving_lines, path.read_text(encoding="utf-8"))
            blocks = _alias_bindings(text)
            for begin, end in _blurred_spans(text):
                body = text[begin:end]
                if PII_RE.search(body) or any(
                    _rendered_expression(output.group(0), begin + output.start(), blocks)
                    for output in OUTPUT_RE.finditer(body)
                ):
                    continue
                line_no = text.count("\n", 0, begin) + 1
                snippet = " ".join(body.split())[:80]
                violations.append(f"{rel_name}:{line_no} blurs {snippet}")
        self.assertEqual(
            violations,
            [],
            "'.sensitive-data' applied to markup containing no personal field "
            "— client codes and invoice numbers are already the privacy-safe "
            f"representation and must stay legible: {violations}",
        )

    def test_known_unprotected_entries_are_still_present(self):
        """Keeps the allowlist from going stale: once a listed render is wrapped
        or deleted, its entry must go too."""
        stale = []
        for rel_name, expressions in KNOWN_UNPROTECTED.items():
            path = TEMPLATES_DIR / rel_name
            if not path.exists():
                stale.append(f"{rel_name} (template no longer exists)")
                continue
            found = {expression for _, expression in _scan(path)}
            stale.extend(f"{rel_name}: {expression}" for expression in sorted(expressions - found))
        self.assertEqual(
            stale,
            [],
            f"KNOWN_UNPROTECTED entries no longer apply — remove them: {stale}",
        )
