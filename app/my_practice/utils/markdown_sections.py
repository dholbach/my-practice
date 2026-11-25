"""Split the clinical profile's markdown into its ``## Heading`` sections.

``ClientProfile.intake_notes`` and ``case_notes`` are single markdown blobs with one
``## `` heading per topic. Several screens need one topic out of them (the log form's
case sheet excerpt today), so the split lives here, once.
"""

import re

_HEADING = re.compile(r"^##[ \t]+(?P<title>.+?)[ \t]*$")
# A prompt line the form template leaves behind, e.g. "**Beginn:**" with nothing after it.
_EMPTY_LABEL = re.compile(r"^\*\*[^*]+:\*\*\s*$")


def split_sections(text: str) -> dict[str, str]:
    """Return ``{heading: body}`` for every ``## `` section, bodies stripped.

    Text before the first heading is ignored. A heading that appears twice keeps its
    first body, so a stray duplicate cannot hide what was written under the original.
    """
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            title = match.group("title")
            current = sections.setdefault(title, []) if title not in sections else None
        elif current is not None:
            current.append(line)
    return {title: "\n".join(lines).strip() for title, lines in sections.items()}


def has_content(body: str) -> bool:
    """True if a section holds anything beyond the template's empty ``**Label:**`` lines."""
    return any(line.strip() and not _EMPTY_LABEL.match(line.strip()) for line in body.splitlines())
