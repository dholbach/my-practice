"""Guardrail for P-038 (English identifiers/comments in code).

test_i18n_coverage.py (P-039) checks a different, narrower thing: that
*user-facing template text* is wrapped for translation and that German
text lives only in the .po msgstr, never as a msgid. It never looks at
.py/.js source at all, so nothing catches a German *identifier* or
*comment* (e.g. issue found during the 2026-08-10 review: `rechnung_pl`
in views/email_views.py — no diacritics, so the i18n test's German-char
regex wouldn't have caught it either).

This is a ratchet, not a finished-state check: KNOWN_VIOLATIONS lists
pre-existing findings not yet cleaned up. Remove an entry from it in the
same PR that fixes it; the test fails if an allowlisted entry turns out
to already be clean, so the list can't go stale in the other direction.

Deliberately narrow scope: this only inspects identifiers (function/class/
variable names) and comments, never string literal *values* — German data
content (email subjects, clinical scaffolding text, tag descriptions) is a
separate, legitimate concern (see CLAUDE.md's i18n/language-policy
exemptions) and is out of scope here by construction.
"""

import ast
import io
import re
import tokenize
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

APP_DIR = Path(settings.BASE_DIR)
PY_SCAN_ROOTS = [APP_DIR / "my_practice"]
JS_SCAN_ROOTS = [APP_DIR / "static" / "js"]

PY_EXCLUDE_DIR_NAMES = {"migrations", "__pycache__"}

# test_i18n_coverage.py's own comments explain the proper-noun exemption it
# uses by naming the actual German terms — meta content, not a violation.
PY_FILE_EXEMPTIONS = {"my_practice/tests/test_i18n_coverage.py"}

# (file, name) pairs already known to violate the policy — fix in the same
# PR you're touching the file, then remove the entry. The word these two
# pre-existing test names use for "total" is ordinary vocabulary, not
# domain-specific like the GebüH-billing terms in TERM_EXEMPTIONS, so they're
# recorded here instead of widening that exemption.
KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    (
        "my_practice/tests/test_gebueh.py",
        "test_gebueh_gesamt_total_shown_when_leistungen_recorded",
    ),
    ("my_practice/tests/test_gebueh.py", "test_gebueh_gesamt_total_hidden_when_no_leistungen"),
}

# Untranslatable German technical/legal terms with no English equivalent,
# used as identifiers throughout the codebase — proper nouns for specific
# German tax filing methods and the licensed-alternative-practitioner fee
# schedule (same rationale as the analogous proper-noun exemption in
# test_i18n_coverage.py), not ordinary vocabulary that should be English.
TERM_EXEMPTIONS = {"gebueh", "gebüh", "eur", "eür", "goa", "leistung"}

GERMAN_CHAR_RE = re.compile(r"[äöüßÄÖÜ]")

# Curated list of unambiguous German domain words that have shown up (or are
# likely to show up) in accidentally-German identifiers/comments. Deliberately
# excludes short grammar words (der/die/das/ist/...) and anything that
# collides with a real English word or existing identifier convention
# (e.g. "tag" is both English and used throughout as ClientTag/PracticeTodo
# vocabulary) to keep false positives low. Expand as real violations turn up.
GERMAN_WORDS = {
    "rechnung",
    "kunde",
    "klient",
    "klientin",
    "zahlung",
    "buchung",
    "ausgabe",
    "einnahme",
    "monat",
    "woche",
    "jahr",
    "stunde",
    "praxis",
    "mitarbeiter",
    "abrechnung",
    "termin",
    "sitzung",
    "behandlung",
    "gebuehr",
    "steuer",
    "anzahl",
    "summe",
    "gesamt",
    "datum",
    "kontostand",
    "ueberweisung",
    "mahnung",
    "saldo",
    "honorar",
    "leistung",
    "anschrift",
    "wohnort",
    "geburtsdatum",
    "telefonnummer",
    "mitteilung",
    "bemerkung",
    "hinweis",
    "fehler",
    "erfolgreich",
    "loeschen",
    "speichern",
    "bearbeiten",
    "erstellen",
    "aktualisieren",
    "pruefen",
    "ueberpruefen",
    "waehrend",
    "wochentag",
    "wochentage",
}
_WORD_ALTERNATION = "|".join(sorted(GERMAN_WORDS, key=len, reverse=True))
GERMAN_WORD_RE = re.compile(rf"\b(?:{_WORD_ALTERNATION})\b", re.IGNORECASE)

CAMEL_SPLIT_RE = re.compile(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])")


def _flag_reason(text: str) -> str | None:
    stripped = TERM_EXEMPTIONS
    lowered = text.lower()
    for term in stripped:
        lowered = lowered.replace(term, "")
    if GERMAN_CHAR_RE.search(lowered):
        return "German diacritic"
    if GERMAN_WORD_RE.search(lowered):
        return "German word"
    return None


def _identifier_parts(name: str):
    """Split snake_case/camelCase into lowercase words for matching."""
    yield name
    for part in name.split("_"):
        yield from CAMEL_SPLIT_RE.findall(part)


def _check_identifier(name: str):
    for part in _identifier_parts(name):
        reason = _flag_reason(part)
        if reason:
            return reason
    return None


def _iter_py_files():
    for root in PY_SCAN_ROOTS:
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(APP_DIR)
            if PY_EXCLUDE_DIR_NAMES & set(rel.parts):
                continue
            if str(rel) in PY_FILE_EXEMPTIONS:
                continue
            yield path


def _iter_js_files():
    for root in JS_SCAN_ROOTS:
        yield from sorted(root.rglob("*.js"))


def _py_identifiers(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name, node.lineno
        elif isinstance(node, ast.arg):
            yield node.arg, node.lineno
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            yield node.id, node.lineno
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            yield node.attr, node.lineno


def _py_comments(source: str):
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok in tokens:
            if tok.type == tokenize.COMMENT:
                yield tok.string.lstrip("#").strip(), tok.start[0]
    except tokenize.TokenizeError, SyntaxError:
        return


JS_COMMENT_RE = re.compile(r"//([^\n]*)|/\*(.*?)\*/", re.DOTALL)
JS_DECL_RE = re.compile(r"\b(?:function|const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)")


class CodeLanguagePolicyTests(SimpleTestCase):
    """P-038: identifiers and comments in .py/.js source must be English."""

    def test_known_violations_are_not_stale(self):
        """Keeps KNOWN_VIOLATIONS from drifting: every entry must correspond
        to a real identifier or comment that still exists (and still
        actually flags) in the file it names."""
        stale = []
        for rel_path, name in sorted(KNOWN_VIOLATIONS):
            full = APP_DIR / rel_path
            if not full.exists():
                stale.append((rel_path, name, "file no longer exists"))
                continue
            source = full.read_text(encoding="utf-8")
            found = False
            if full.suffix == ".py":
                try:
                    tree = ast.parse(source, filename=str(full))
                    found = any(n == name for n, _ in _py_identifiers(tree))
                    found = found or any(c == name for c, _ in _py_comments(source))
                except SyntaxError:
                    pass
            else:
                found = name in source
            if not found:
                stale.append((rel_path, name, "no longer present in file"))
        self.assertEqual(
            stale,
            [],
            f"KNOWN_VIOLATIONS has stale entries — remove them: {stale}",
        )

    def test_python_identifiers_and_comments_are_english(self):
        violations = []
        for path in _iter_py_files():
            rel = str(path.relative_to(APP_DIR))
            source = path.read_text(encoding="utf-8")

            try:
                tree = ast.parse(source, filename=str(path))
            except SyntaxError:
                continue

            for name, lineno in _py_identifiers(tree):
                reason = _check_identifier(name)
                if reason and (rel, name) not in KNOWN_VIOLATIONS:
                    violations.append(f"{rel}:{lineno}: identifier '{name}' ({reason})")

            for comment, lineno in _py_comments(source):
                reason = _flag_reason(comment)
                if reason and (rel, comment) not in KNOWN_VIOLATIONS:
                    violations.append(f"{rel}:{lineno}: comment {comment!r} ({reason})")

        self.assertEqual(
            violations,
            [],
            "Non-English identifiers/comments found (P-038) — translate them, or if "
            "genuinely untranslatable domain terminology, add to TERM_EXEMPTIONS "
            "(not KNOWN_VIOLATIONS, which is only for pre-existing debt):\n"
            + "\n".join(violations),
        )

    def test_js_identifiers_and_comments_are_english(self):
        violations = []
        for path in _iter_js_files():
            rel = str(path.relative_to(APP_DIR))
            source = path.read_text(encoding="utf-8")

            for match in JS_COMMENT_RE.finditer(source):
                comment = (match.group(1) or match.group(2) or "").strip()
                reason = _flag_reason(comment)
                if reason and (rel, comment) not in KNOWN_VIOLATIONS:
                    lineno = source.count("\n", 0, match.start()) + 1
                    violations.append(f"{rel}:{lineno}: comment {comment!r} ({reason})")

            for match in JS_DECL_RE.finditer(source):
                name = match.group(1)
                reason = _check_identifier(name)
                if reason and (rel, name) not in KNOWN_VIOLATIONS:
                    lineno = source.count("\n", 0, match.start()) + 1
                    violations.append(f"{rel}:{lineno}: identifier '{name}' ({reason})")

        self.assertEqual(
            violations,
            [],
            "Non-English identifiers/comments found in JS (P-038):\n" + "\n".join(violations),
        )
