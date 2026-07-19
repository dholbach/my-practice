"""Guardrail for P-039 (issue #69): keeps the i18n sweep from regressing.

This is a ratchet, not a finished-state check. ``KNOWN_UNWRAPPED_TEMPLATES``
lists templates that are not yet wrapped — remove an entry from it in the
same PR that wraps that template (Phase 1 of the sweep). The test fails if
an allowlisted template turns out to already be fully wrapped, so the list
can't go stale in the other direction either.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

TEMPLATES_DIR = Path(settings.BASE_DIR) / "templates"
LOCALE_DIR = Path(settings.BASE_DIR) / "locale"

# Handle language per-document (client language field), not via Django i18n.
EXEMPT_TEMPLATES = {
    "my_practice/invoice_pdf_de.html",
    "my_practice/invoice_pdf_en.html",
    "my_practice/treatment_contract_pdf.html",
    "my_practice/intake_form_pdf.html",
    "my_practice/questionnaire_pdf.html",
}

# Templates not yet wrapped for i18n — tracked as the Phase 1 backlog of the
# dedicated P-039 sweep (issue #69). Remove an entry here in the same PR that
# wraps it with {% load i18n %} + {% trans %}/{% blocktrans %}.
KNOWN_UNWRAPPED_TEMPLATES = {
    "includes/agenda_widget_content.html",
    "includes/agenda_widget.html",
    "includes/bank_import_widget_content.html",
    "includes/calendar_preflight_widget.html",
    "includes/checklist_widget_content.html",
    "includes/client_tags.html",
    "includes/email_card.html",
    "includes/empty_state.html",
    "includes/inline_post_button.html",
    "includes/invoice_actions_widget_content.html",
    "includes/invoice_status_badge.html",
    "includes/pagination.html",
    "includes/stat_card.html",
    "includes/stats_grid.html",
    "includes/weekly_focus_widget_content.html",
    "includes/widget_base.html",
    "my_practice/bank_expense_review.html",
    "my_practice/bank_import.html",
    "my_practice/bank_withdrawal_review.html",
    "my_practice/boilerplate.html",
    "my_practice/calendar_approval_queue.html",
    "my_practice/calendar_import.html",
    "my_practice/client_detail_documents.html",
    "my_practice/client_list.html",
    "my_practice/client_triage.html",
    "my_practice/expense_form.html",
    "my_practice/invoice_list.html",
    "my_practice/marketing_period_form.html",
    "my_practice/monthly_billing_overview.html",
    "my_practice/practice_select.html",
    "my_practice/send_cancellation_email.html",
    "my_practice/supervision_queue.html",
    "my_practice/tax_workday_audit.html",
    "my_practice/tax_year_summary.html",
    "my_practice/todo_list.html",
}

LOAD_I18N_RE = re.compile(r"{%\s*load[^%]*\bi18n\b[^%]*%}")

# "GebüH" (Gebührenverzeichnis für Heilpraktiker) is a proper noun for the
# official German fee schedule — kept verbatim in both languages, not
# translated. It's the one legitimate source of German diacritics in an
# otherwise-English msgid/template string.
GEBUEH_RE = re.compile(r"Gebü[hH]")
GERMAN_CHAR_RE = re.compile(r"[äöüßÄÖÜ]")

COMMENT_RE = re.compile(r"{%\s*comment\s*%}.*?{%\s*endcomment\s*%}|{#.*?#}|<!--.*?-->", re.DOTALL)
SCRIPT_STYLE_RE = re.compile(
    r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE
)


def _all_templates():
    for path in sorted(TEMPLATES_DIR.rglob("*.html")):
        yield path, str(path.relative_to(TEMPLATES_DIR)).replace("\\", "/")


def _strip_noise(text):
    text = SCRIPT_STYLE_RE.sub("", text)
    text = COMMENT_RE.sub("", text)
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
