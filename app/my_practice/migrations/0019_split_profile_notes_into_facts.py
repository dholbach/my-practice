"""Split the profile's intake notes, case notes and working diagnosis into case sheet lines.

``ClientProfile.intake_notes`` and ``case_notes`` hold one markdown section per topic
(``## Anliegen`` …). Each filled section becomes one or more ``ClinicalFact`` lines, dated
with the day the profile was last saved. Nothing is lost:

- a labelled value inside a section (``**Beginn:** …``) goes to that cell of its row;
- bullet lists in a multi-line row become one line per bullet;
- text that matches no row (an unknown heading, text before the first heading, the old
  "Verlauf" section) goes to "Weitere Notizen" together with its heading;
- the old fields stay on ClientProfile, untouched.

The parser is self-contained on purpose: a migration must keep working when the app code it
once used has changed, and it has no business importing it.
"""

import re
import unicodedata

from django.db import migrations

# heading (normalised, see _norm) -> (kind, {normalised label -> cell key})
INTAKE_HEADINGS = {
    "anliegen": ("concern", {}),
    "symptomatik": (
        "symptoms",
        {"beginn": "onset", "verschlimmerung/anderung": "change", "dauer bis": "until"},
    ),
    "korperlich": ("physical", {}),
    "affektiv": ("affective", {}),
    "erst-ausloser": ("first_trigger", {}),
    "aktuelle trigger": ("current_triggers", {}),
    "anamnestische besonderheiten": ("history", {}),
    "nervensystem/ans": (
        "ans",
        {"erregungslage/grundmuster": "arousal", "erregungslage, grundmuster": "arousal"},
    ),
    "limbisches system": (
        "limbic",
        {
            "nahe-/distanzmuster": "closeness",
            "empathiefahigkeit": "empathy",
            "loyalitat/scham/schuld": "loyalty",
        },
    ),
    "neocortical": (
        "neocortical",
        {"prasenz/fokusstabilitat": "presence", "mentalisationsgrad": "mentalization"},
    ),
    "glaubenssatze": ("beliefs", {}),
    "sibam-elemente": ("sibam", {"bevorzugt": "preferred", "fehlend": "missing"}),
    "ressourcen": ("resources", {}),
    "arbeitshypothese": ("hypothesis", {}),
    "arbeitsdiagnose": ("diagnosis", {}),
    "therapieziel (patient)": ("goal", {}),
    "sicherheit gestort durch": ("safety", {}),
    "prozessaufbau": ("process", {}),
    "themen": ("themes", {}),
    "familiendynamik": ("family", {}),
    "ich-du": ("i_thou", {}),
    "herausforderungen": ("challenges", {}),
    "zukunftige arbeit/fragen": ("future_work", {}),
}
MULTI_KINDS = {
    "physical",
    "affective",
    "current_triggers",
    "beliefs",
    "resources",
    "themes",
    "family",
    "i_thou",
    "challenges",
    "future_work",
}

_HEADING = re.compile(r"^##[ \t]+(?P<title>.+?)[ \t]*$")
_LABELLED = re.compile(r"^\*\*(?P<label>[^*]+?):\*\*[ \t]*(?P<rest>.*)$")
_EMPTY_LABEL = re.compile(r"^\*\*[^*]+:\*\*\s*$")
_BULLET = re.compile(r"^\s*[-*•][ \t]+")


def _norm(text: str) -> str:
    """Compare headings and labels loosely: case, diacritics, quotes and spaces around "/"."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[\"'“”„‚‘’`]", "", text)
    text = re.sub(r"\s*/\s*", "/", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def _has_content(body: str) -> bool:
    return any(line.strip() and not _EMPTY_LABEL.match(line.strip()) for line in body.splitlines())


def _split(text: str) -> tuple[str, list[tuple[str, str]]]:
    """The text before the first ``## `` heading, and the (heading, body) sections after it."""
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            sections.append((match.group("title"), []))
        elif sections:
            sections[-1][1].append(line)
        else:
            preamble.append(line)
    return "\n".join(preamble).strip(), [(h, "\n".join(b).strip()) for h, b in sections]


def _bullets(body: str) -> list[str] | None:
    """The bullets of a body made only of bullet lines (continuation lines kept), else None."""
    items: list[list[str]] = []
    for line in body.splitlines():
        if not line.strip():
            continue
        if _BULLET.match(line):
            items.append([_BULLET.sub("", line, count=1).strip()])
        elif items and line.startswith((" ", "\t")):
            items[-1].append(line.strip())
        else:
            return None
    return ["\n".join(item) for item in items] or None


def _labelled(body: str, labels: dict[str, str]) -> tuple[dict[str, str], str]:
    """Split a body into {cell key: value} for the known ``**Label:**`` blocks, and the rest."""
    values: dict[str, list[str]] = {}
    rest: list[str] = []
    current: list[str] | None = None
    for line in body.splitlines():
        match = _LABELLED.match(line.strip())
        key = labels.get(_norm(match.group("label"))) if match else None
        if key:
            current = values.setdefault(key, [])
            current.append(match.group("rest"))
        elif match:  # a label this row does not know: keep it, whole, as a leftover
            current = None
            rest.append(line)
        elif current is not None:
            current.append(line)
        else:
            rest.append(line)
    return {k: "\n".join(v).strip() for k, v in values.items()}, "\n".join(rest).strip()


def legacy_to_facts(intake_notes: str, case_notes: str, diagnosis: str) -> list[tuple[str, str, str]]:
    """The ``(kind, sub, content)`` lines for one profile, in reading order."""
    facts: list[tuple[str, str, str]] = []
    diagnosis = (diagnosis or "").strip()
    if diagnosis:
        facts.append(("diagnosis", "", diagnosis))

    for text in (intake_notes or "", case_notes or ""):
        preamble, sections = _split(text)
        if preamble:
            facts.append(("notes", "", preamble))
        for heading, body in sections:
            known = INTAKE_HEADINGS.get(_norm(heading))
            if not _has_content(body):
                continue
            if not known:
                facts.append(("notes", "", f"## {heading}\n{body}"))
                continue
            kind, labels = known
            if kind == "diagnosis":
                if diagnosis and body.strip() != diagnosis:  # the field wins; keep the other text
                    facts.append(("notes", "", f"## {heading}\n{body}"))
                elif not diagnosis:
                    facts.append(("diagnosis", "", body))
                continue
            if labels:
                values, rest = _labelled(body, labels)
                facts.extend((kind, key, value) for key, value in values.items() if value)
                if _has_content(rest):
                    facts.append(("notes", "", f"## {heading}\n{rest}"))
                continue
            items = _bullets(body) if kind in MULTI_KINDS else None
            facts.extend((kind, "", item) for item in (items or [body]))
    return facts


def split_profiles(apps, schema_editor):
    ClientProfile = apps.get_model("my_practice", "ClientProfile")
    ClinicalFact = apps.get_model("my_practice", "ClinicalFact")
    for profile in ClientProfile.objects.all().iterator():
        if ClinicalFact.objects.filter(client_id=profile.client_id).exists():
            continue  # already split (the migration was run before, or the sheet is in use)
        noted_on = profile.updated_at.date()
        ClinicalFact.objects.bulk_create(
            [
                ClinicalFact(client_id=profile.client_id, kind=kind, sub=sub, content=content, noted_on=noted_on)
                for kind, sub, content in legacy_to_facts(
                    profile.intake_notes, profile.case_notes, profile.arbeitsdiagnose
                )
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("my_practice", "0018_clinical_fact"),
    ]

    operations = [
        # Reversing leaves the lines to the schema migration before it, which drops them.
        migrations.RunPython(split_profiles, migrations.RunPython.noop),
    ]
