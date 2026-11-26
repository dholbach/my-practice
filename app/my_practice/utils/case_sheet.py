"""Reading and changing a client's case sheet (P-006).

The views stay thin: they validate the request and call these functions. Nothing here
deletes a line. Changing one supersedes it, closing one resolves it, so the earlier wording
and its date stay on record.
"""

from dataclasses import dataclass, field
from datetime import date

from django.db import transaction
from django.utils import timezone

from ..models import Client, Session
from ..models.case_sheet import CASE_SHEET_ROWS, ROWS_BY_KIND, ClinicalFact, SheetRow, cell_keys

ACTIVE = ClinicalFact.Status.ACTIVE
MAX_LINE_LENGTH = 5000


@dataclass
class CellView:
    """One cell as the template shows it: its current lines and the earlier ones."""

    row: SheetRow
    key: str
    label: str
    lines: list[ClinicalFact] = field(default_factory=list)
    history: list[ClinicalFact] = field(default_factory=list)

    @property
    def multi(self) -> bool:
        return self.row.multi

    @property
    def current(self) -> ClinicalFact | None:
        """The one current line of a single-line cell."""
        return self.lines[0] if self.lines else None


@dataclass
class RowView:
    row: SheetRow
    cells: list[CellView]

    @property
    def has_cells(self) -> bool:
        return bool(self.row.cells)


def build_case_sheet(client: Client) -> list[RowView]:
    """Every row of the sheet with its cells' current lines and history, in sheet order."""
    by_cell: dict[tuple[str, str], list[ClinicalFact]] = {}
    facts = (
        ClinicalFact.objects.filter(client=client)
        .select_related("source_session__log")
        .order_by("noted_on", "pk")
    )
    for fact in facts:
        by_cell.setdefault((fact.kind, fact.sub), []).append(fact)

    rows = []
    for row in CASE_SHEET_ROWS:
        labels = {cell.key: cell.label for cell in row.cells}
        cells = []
        for key in cell_keys(row):
            facts = by_cell.get((row.kind, key), [])
            cells.append(
                CellView(
                    row=row,
                    key=key,
                    label=labels.get(key, ""),
                    lines=[f for f in facts if f.status == ACTIVE],
                    # Newest first: what was written just before is what you look for
                    history=[f for f in reversed(facts) if f.status != ACTIVE],
                )
            )
        rows.append(RowView(row=row, cells=cells))
    return rows


def active_lines(client: Client, kind: str, sub: str | None = None) -> list[ClinicalFact]:
    """The current lines of one row (all its cells, or just ``sub``), oldest first."""
    lines = ClinicalFact.objects.filter(client=client, kind=kind, status=ACTIVE)
    if sub is not None:
        lines = lines.filter(sub=sub)
    return list(lines)


def working_diagnosis(client: Client, *, sheet: list[RowView] | None = None) -> str:
    """The current working diagnosis (Arbeitsdiagnose), or "" when there is none.

    Pass the already built ``sheet`` to read it from there instead of querying again.
    """
    if sheet is not None:
        lines = [
            line for row in sheet if row.row.kind == "diagnosis" for line in row.cells[0].lines
        ]
    else:
        lines = active_lines(client, "diagnosis")
    return lines[-1].content if lines else ""


def describe_fact(fact: ClinicalFact) -> dict[str, str]:
    """A line with the labels of its row and cell, as the digest and review lists show it."""
    row = ROWS_BY_KIND.get(fact.kind)
    cell = next((c.label for c in row.cells if c.key == fact.sub), "") if row else ""
    return {"row": row.label if row else fact.kind, "cell": cell, "content": fact.content}


def lines_to_markdown(lines: list[ClinicalFact]) -> str:
    """One line as it is, several as a bullet list (for showing a cell where there is room for text)."""
    if len(lines) == 1:
        return lines[0].content
    return "\n".join(f"- {line.content}" for line in lines)


def clean_content(raw: str) -> str:
    """A line as typed: surrounding whitespace removed, cut to the length limit."""
    return raw.strip()[:MAX_LINE_LENGTH]


def valid_cell(kind: str, sub: str) -> bool:
    """Whether ``kind`` is a row of the sheet and ``sub`` one of its cells."""
    row = ROWS_BY_KIND.get(kind)
    return row is not None and sub in cell_keys(row)


@transaction.atomic
def add_line(
    client: Client,
    kind: str,
    sub: str,
    content: str,
    *,
    source_session: Session | None = None,
    today: date | None = None,
) -> ClinicalFact | None:
    """Add a line to a cell. In a single-line cell it supersedes the current line.

    Returns the new line, or None when ``content`` is empty or the cell does not exist.
    """
    content = clean_content(content)
    if not content or not valid_cell(kind, sub):
        return None
    today = today or timezone.localdate()
    fact = ClinicalFact.objects.create(
        client=client,
        kind=kind,
        sub=sub,
        content=content,
        noted_on=today,
        source_session=source_session,
    )
    if not ROWS_BY_KIND[kind].multi:
        for old in active_lines(client, kind, sub):
            if old.pk != fact.pk:
                _close(old, ClinicalFact.Status.SUPERSEDED, today, superseded_by=fact)
    return fact


@transaction.atomic
def change_line(
    fact: ClinicalFact, content: str, *, today: date | None = None
) -> ClinicalFact | None:
    """Reword a line: the new wording is a new line, the old one is superseded by it.

    Returns the new line, or None when the wording is empty or unchanged, or when the line
    is no longer current.
    """
    content = clean_content(content)
    if not content or content == fact.content or fact.status != ACTIVE:
        return None
    today = today or timezone.localdate()
    new = ClinicalFact.objects.create(
        client=fact.client,
        kind=fact.kind,
        sub=fact.sub,
        content=content,
        noted_on=today,
        source_session=fact.source_session,
    )
    _close(fact, ClinicalFact.Status.SUPERSEDED, today, superseded_by=new)
    return new


def resolve_line(fact: ClinicalFact, *, today: date | None = None) -> bool:
    """Mark a line as no longer applying. False when it was not current."""
    if fact.status != ACTIVE:
        return False
    _close(fact, ClinicalFact.Status.RESOLVED, today or timezone.localdate())
    return True


def _close(
    fact: ClinicalFact, status: str, today: date, *, superseded_by: ClinicalFact | None = None
) -> None:
    fact.status = status
    fact.closed_on = today
    fact.superseded_by = superseded_by
    fact.save(update_fields=["status", "closed_on", "superseded_by", "updated_at"])
