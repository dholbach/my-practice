"""Only ``post_json.js`` reads the CSRF token and writes the CSRF header.

Eight page scripts used to read ``<body data-csrf-token>`` themselves, one read the
``csrftoken`` cookie with its own ``getCookie``, and four built a ``csrfmiddlewaretoken``
form field by hand: three ways to get the same token, each a place to get a POST
wrong (or to leave the token out) and none of them visible to the test client.
``MPHttp.csrfToken()`` / ``postJson()`` / ``postForm()`` in ``static/js/post_json.js``
are now the one way; a script that must carry the token as a hidden input of a DOM
form (``ui_actions.js``) asks ``MPHttp.csrfToken()``.

The scan is plain text over the non-test scripts, so it also catches the token read
in a comment that someone later turns into code. ``KNOWN_TOKEN_READERS`` is a ratchet
like the other guardrails: shrink it, never grow it to make a new script pass.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

JS_DIR = Path(settings.BASE_DIR) / "static" / "js"

# The one file that may read the token from the page and set the header.
SOURCE_OF_TRUTH = "post_json.js"

# Script files that still do it themselves.
KNOWN_TOKEN_READERS: set[str] = set()

# A read of the page token, the cookie, or a hand-set CSRF header.
TOKEN_ACCESS = re.compile(
    r"dataset\.csrfToken|dataset\[['\"]csrfToken['\"]\]|X-CSRFToken|getCookie\(|['\"]csrftoken['\"]",
    re.IGNORECASE,
)


def _scripts():
    for path in sorted(JS_DIR.glob("*.js")):
        if path.name.endswith(".test.js") or path.name.endswith(".test.extended.js"):
            continue
        if path.name.startswith(("chart.umd", "alpine-csp")):  # vendored libraries
            continue
        yield path


def _code_lines(path):
    """The lines of a script outside ``/* ... */`` and ``//`` comments."""
    text = re.sub(
        r"/\*.*?\*/", lambda match: "\n" * match.group(0).count("\n"), path.read_text(), flags=re.S
    )
    for number, line in enumerate(text.splitlines(), start=1):
        yield number, line.split("//", 1)[0]


class CsrfSingleSourceTests(SimpleTestCase):
    def test_the_source_of_truth_exists_and_reads_the_token(self):
        text = (JS_DIR / SOURCE_OF_TRUTH).read_text()
        self.assertIn("dataset.csrfToken", text)
        self.assertIn("X-CSRFToken", text)

    def test_no_other_script_reads_the_token_or_sets_the_header(self):
        offenders = []
        for path in _scripts():
            if path.name == SOURCE_OF_TRUTH or path.name in KNOWN_TOKEN_READERS:
                continue
            for number, line in _code_lines(path):
                if TOKEN_ACCESS.search(line):
                    offenders.append(f"{path.name}:{number}: {line.strip()}")
        self.assertEqual(
            offenders,
            [],
            "Send POSTs through MPHttp.postForm / postJson and ask MPHttp.csrfToken() for the "
            "token (static/js/post_json.js); do not read it from the page or the cookie.",
        )

    def test_allowlist_has_no_stale_entries(self):
        readers = set()
        for path in _scripts():
            if path.name == SOURCE_OF_TRUTH:
                continue
            if any(TOKEN_ACCESS.search(line) for _, line in _code_lines(path)):
                readers.add(path.name)
        self.assertEqual(sorted(KNOWN_TOKEN_READERS - readers), [])

    def test_the_scan_finds_each_way_of_getting_the_token(self):
        for line in (
            "const t = document.body.dataset.csrfToken;",
            'headers: { "X-CSRFToken": token }',
            'const t = getCookie("csrftoken");',
        ):
            self.assertTrue(TOKEN_ACCESS.search(line), line)
        self.assertFalse(TOKEN_ACCESS.search("MPHttp.postForm(url, fields)"))
        self.assertFalse(TOKEN_ACCESS.search("token.value = MPHttp.csrfToken();"))
