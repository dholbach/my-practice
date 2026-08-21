"""Guardrail for P-039 (issue #69): keeps the i18n sweep from regressing.

This is a ratchet, not a finished-state check. ``KNOWN_UNWRAPPED_TEMPLATES``
lists templates that are not yet wrapped — remove an entry from it in the
same PR that wraps that template (Phase 1 of the sweep). The test fails if
an allowlisted template turns out to already be fully wrapped, so the list
can't go stale in the other direction either.
"""

import ast
import os
import re
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase

TEMPLATES_DIR = Path(settings.BASE_DIR) / "templates"
LOCALE_DIR = Path(settings.BASE_DIR) / "locale"

# Handle language per-document (client language field), not via Django i18n.
# includes/email_card.html is here too: its labels (Betreff/Subject,
# Kopieren/Copy) identify the language of the authored bilingual content next
# to them, not the app's UI language — same rationale as utils/email_utils.py.
EXEMPT_TEMPLATES = {
    "my_practice/invoice_pdf_de.html",
    "my_practice/invoice_pdf_en.html",
    "my_practice/treatment_contract_pdf.html",
    "my_practice/intake_form_pdf.html",
    "my_practice/questionnaire_pdf.html",
    "includes/email_card.html",
}

# Templates not yet wrapped for i18n — tracked as the Phase 1 backlog of the
# dedicated P-039 sweep (issue #69). Remove an entry here in the same PR that
# wraps it with {% load i18n %} + {% trans %}/{% blocktrans %}.
KNOWN_UNWRAPPED_TEMPLATES: set[str] = set()

LOAD_I18N_RE = re.compile(r"{%\s*load[^%]*\bi18n\b[^%]*%}")

# Proper nouns/abbreviations for German tax and legal terms kept verbatim in
# both languages, not translated — "GebüH" (Gebührenverzeichnis für
# Heilpraktiker, the official fee schedule) and "EÜR" (Einnahmenüberschuss-
# rechnung, the income/expense statement tax filing method). These are the
# only legitimate sources of German diacritics in an otherwise-English
# msgid/template string.
GEBUEH_RE = re.compile(r"Gebü[hH]|EÜR")
GERMAN_CHAR_RE = re.compile(r"[äöüßÄÖÜ]")

COMMENT_RE = re.compile(r"{%\s*comment\s*%}.*?{%\s*endcomment\s*%}|{#.*?#}|<!--.*?-->", re.DOTALL)
# Only <style> is stripped — CSS won't contain prose. <script> is deliberately
# NOT stripped: templates embed {% trans %} inside alert()/JS string literals
# (see includes/client_tags.html), and a leaked German alert() string is a
# real bug the same as leaked HTML text — a past version of this regex
# excluded <script> too and missed exactly that.
STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)

# Narrow, explicit escape hatch for non-UI German inside <script> — e.g. filename
# keyword-matching against German filenames a user might upload. Not a general
# exemption: mark only the specific literal, keep it as tight as possible.
JS_EXEMPT_RE = re.compile(r"/\*\s*i18n-exempt-start.*?\*/.*?/\*\s*i18n-exempt-end\s*\*/", re.DOTALL)


def _parse_po_msgids(path):
    """Return every non-empty msgid/msgid_plural in a .po file.

    Deliberately minimal (not a full .po parser): each quoted line is a valid
    Python string literal too (.po C-style escaping is a subset of Python's),
    so ast.literal_eval unescapes it correctly without reimplementing gettext's
    escaping rules.
    """
    msgids = set()
    lines = path.read_text(encoding="utf-8").splitlines()
    i, n = 0, len(lines)
    while i < n:
        line = lines[i].strip()
        for prefix in ("msgid_plural ", "msgid "):
            if line.startswith(prefix):
                parts = [line[len(prefix) :]]
                i += 1
                while i < n and lines[i].strip().startswith('"'):
                    parts.append(lines[i].strip())
                    i += 1
                msgid = "".join(ast.literal_eval(part) for part in parts)
                if msgid:
                    msgids.add(msgid)
                break
        else:
            i += 1
    return msgids


def _all_templates():
    for path in sorted(TEMPLATES_DIR.rglob("*.html")):
        yield path, str(path.relative_to(TEMPLATES_DIR)).replace("\\", "/")


def _strip_noise(text):
    text = STYLE_RE.sub("", text)
    text = COMMENT_RE.sub("", text)
    text = JS_EXEMPT_RE.sub("", text)
    return GEBUEH_RE.sub("", text)


class TemplateI18nCoverageTests(SimpleTestCase):
    """Every non-exempt template must load i18n; wrapped templates must not
    leak raw German text."""

    def test_known_unwrapped_templates_still_exist(self):
        missing = sorted(
            name for name in KNOWN_UNWRAPPED_TEMPLATES if not (TEMPLATES_DIR / name).exists()
        )
        self.assertEqual(
            missing,
            [],
            f"KNOWN_UNWRAPPED_TEMPLATES references templates that no longer "
            f"exist — remove them from the allowlist: {missing}",
        )

    def test_non_exempt_templates_load_i18n(self):
        violations = []
        for path, rel_name in _all_templates():
            if rel_name in EXEMPT_TEMPLATES or rel_name in KNOWN_UNWRAPPED_TEMPLATES:
                continue
            content = path.read_text(encoding="utf-8")
            if not LOAD_I18N_RE.search(content):
                violations.append(rel_name)
        self.assertEqual(
            violations,
            [],
            "Templates missing '{% load i18n %}' — either wrap them or add "
            f"to KNOWN_UNWRAPPED_TEMPLATES in this test: {violations}",
        )

    def test_wrapped_templates_have_no_leaked_german_text(self):
        """A template claiming to be wrapped (not on the backlog list) must
        not contain raw German characters — msgids are English per
        CLAUDE.md; German lives only in locale/de/LC_MESSAGES/django.po."""
        violations = []
        for path, rel_name in _all_templates():
            if rel_name in EXEMPT_TEMPLATES or rel_name in KNOWN_UNWRAPPED_TEMPLATES:
                continue
            content = _strip_noise(path.read_text(encoding="utf-8"))
            if GERMAN_CHAR_RE.search(content):
                violations.append(rel_name)
        self.assertEqual(
            violations,
            [],
            "Templates marked as wrapped still contain raw German "
            f"characters outside the 'GebüH' proper noun: {violations}",
        )

    def test_known_unwrapped_templates_are_not_already_wrapped(self):
        """Keeps the allowlist from going stale: once a listed template is
        fully wrapped, it must be removed here (not left dead)."""
        already_wrapped = []
        for name in sorted(KNOWN_UNWRAPPED_TEMPLATES):
            path = TEMPLATES_DIR / name
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8")
            if not LOAD_I18N_RE.search(content):
                continue
            if not GERMAN_CHAR_RE.search(_strip_noise(content)):
                already_wrapped.append(name)
        self.assertEqual(
            already_wrapped,
            [],
            "Templates in KNOWN_UNWRAPPED_TEMPLATES are already fully "
            f"wrapped — remove them from the allowlist: {already_wrapped}",
        )


class TranslationCatalogTests(SimpleTestCase):
    """makemessages sometimes guesses a fuzzy translation from an unrelated
    similarly-worded msgid — those guesses must be fixed before commit."""

    def test_no_fuzzy_entries_in_catalogs(self):
        for lang in ("de", "en"):
            po_path = LOCALE_DIR / lang / "LC_MESSAGES" / "django.po"
            with self.subTest(lang=lang):
                self.assertTrue(po_path.exists(), f"missing {po_path}")
                content = po_path.read_text(encoding="utf-8")
                fuzzy_count = len(re.findall(r"^#, fuzzy", content, re.MULTILINE))
                self.assertEqual(
                    fuzzy_count,
                    0,
                    f"{po_path} has {fuzzy_count} fuzzy entries — fix the "
                    "msgstr and remove the fuzzy marker before committing.",
                )

    def test_no_unextracted_strings(self):
        """Regression test for issue #376: a template/source string wrapped in
        {% trans %}/{% blocktrans %}/gettext() but never run through
        makemessages silently falls back to the raw English msgid in the
        German UI — the other tests in this file don't catch that, since the
        template itself looks fully wrapped.

        Re-runs extraction into a scratch copy of the source tree (so the
        real working-tree catalogs are never touched) and diffs its msgid set
        against the committed catalog. Anything present only in the fresh
        extraction was never captured by a prior `./dev.py i18n` run.
        """
        tmp_dir = tempfile.mkdtemp(prefix="i18n-coverage-")
        self.addCleanup(shutil.rmtree, tmp_dir, ignore_errors=True)
        for name in ("templates", "my_practice", "config", "locale"):
            shutil.copytree(
                Path(settings.BASE_DIR) / name,
                Path(tmp_dir) / name,
                ignore=shutil.ignore_patterns("__pycache__"),
            )

        cwd = os.getcwd()
        os.chdir(tmp_dir)
        try:
            call_command("makemessages", "-l", "de", "--no-wrap", verbosity=0)
        finally:
            os.chdir(cwd)

        fresh_po = Path(tmp_dir) / "locale" / "de" / "LC_MESSAGES" / "django.po"
        committed_po = LOCALE_DIR / "de" / "LC_MESSAGES" / "django.po"
        missing = sorted(_parse_po_msgids(fresh_po) - _parse_po_msgids(committed_po))
        self.assertEqual(
            missing,
            [],
            "Strings found in templates/source but missing from "
            "locale/de/LC_MESSAGES/django.po — run `./dev.py i18n`, fill in "
            f"the new msgstr(s), and commit the result: {missing}",
        )
