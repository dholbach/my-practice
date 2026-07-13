"""
Loader for clinical questionnaire content (question text, response scales).

Content is kept separate from the rendering template so instruments with
restrictive licensing (e.g. BDI-II, ADNM-20) never have to enter this
public repo's git history — only the generic rendering shell is committed.
Public-domain instruments (e.g. GAD-7) can ship as an in-repo content file;
everything else is placed by the practice owner under
``PAYMENTS_DATA_DIR/questionnaires/<code>.json`` at runtime and is never
committed. See docs/projects/todo/P-118_QUESTIONNAIRE_PDFS.md.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

CONTENT_DIR = Path(__file__).resolve().parent.parent / "questionnaire_content"


class QuestionnaireNotFoundError(Exception):
    """No content file exists for the requested instrument code."""


@dataclass
class QuestionnaireContent:
    """Raw, unresolved content — ``sections`` still carries per-language dicts.

    Each section is a dict with a ``type`` key resolved by
    ``views.api_views._resolve_questionnaire_section``: ``grid`` (statement
    rows x response columns), ``checklist`` (statement rows with a single
    yes/no checkbox), or ``freetext`` (a prompt with N blank fillable
    lines). Every section type may also carry an optional ``intro`` dict.
    """

    code: str
    title: dict[str, str]
    intro: dict[str, str]
    sections: list[dict]


def _content_path(code: str) -> Path | None:
    instance_path = settings.PAYMENTS_DATA_DIR / "questionnaires" / f"{code}.json"
    if instance_path.exists():
        return instance_path
    shipped_path = CONTENT_DIR / f"{code}.json"
    if shipped_path.exists():
        return shipped_path
    return None


def load_questionnaire(code: str) -> QuestionnaireContent:
    """Load questionnaire content by instrument code.

    Looks under ``PAYMENTS_DATA_DIR/questionnaires/`` first (instance-local,
    for licensed instruments the practice owner supplies themselves), then
    falls back to the content shipped with the app (for public-domain
    instruments).
    """
    path = _content_path(code)
    if path is None:
        raise QuestionnaireNotFoundError(
            f"No content file found for questionnaire '{code}'. Place it at "
            f"{settings.PAYMENTS_DATA_DIR / 'questionnaires' / f'{code}.json'}"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return QuestionnaireContent(
        code=data["code"],
        title=data["title"],
        intro=data.get("intro", {}),
        sections=data["sections"],
    )
