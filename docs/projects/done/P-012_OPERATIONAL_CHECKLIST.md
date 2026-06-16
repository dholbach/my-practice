# P-012: Operational Checklist (Backup & Recovery Automation)

**Status**: ✅ DONE
**Completed**: 3. März 2026
**Effort**: ~5h (Model + Views + Templates + Pause-Feature + Tests)
**Commit**: `fff8711`

## Ergebnis

In-App Checklisten für operative Backup- und Recovery-Prozeduren — direkt verknüpft mit den P-011 Backup-Prozeduren. Alle 4 Checklisten-Typen (wöchentlich, monatlich, vierteljährlich, jährlich) sind implementiert, inklusive Pause-Feature für einzelne Punkte.

## Implementierte Features

### Checklisten-Typen (4 Cadences)

| Typ | Periode | Elemente | Zweck |
|-----|---------|----------|-------|
| `weekly` | Jede Woche (Montag) | 5 | USB-Backup + NAS-Trigger verifizieren |
| `monthly` | Erster des Monats | 6 | Restore-Smoke-Test (Datenbank + Mediendatei) |
| `quarterly` | Quartalserster | 6 | MicroSD-Offsite-Backup (Karte A/B im Wechsel, alle 2 Wochen) |
| `annual` | 1. Januar | 5 | Vollständiger Restore-Test + Sicherheitsreview |

### Pause-Feature (Einzelne Punkte)

Ermöglicht, einzelne Checklisten-Punkte zeitweise zu pausieren — z.B. wenn neue MicroSD-Karten noch bestellt werden:

- **Unbegrenzt**: Kein Enddatum → bleibt aktiv bis manuell aufgehoben
- **Zeitlich begrenzt**: Datum angeben → Pause läuft automatisch ab
- **Update**: Erneutes Pausieren ersetzt den vorherigen Eintrag (`update_or_create`)
- **Widget-Logik**: Wenn alle Punkte eines Typs pausiert sind → kein Widget (nichts Actionables)

### Dashboard-Widget

- Zeigt ausstehende Checklisten mit Badge-Anzahl
- Collapsed by default, öffnet auf Klick
- Unterscheidet "N fällig" (warning) von "✅ Erledigt"

## Datenmodell

```python
# my_practice/models/operational.py

class OperationalChecklistCompletion:
    checklist_type: str           # weekly / monthly / quarterly / annual
    year_month: DateField         # Erster Tag der Periode (z.B. 2026-03-01)
    completed_at: DateTimeField   # Abschluss-Zeitstempel (nullable)
    notes: TextField              # Optionale Notizen (z.B. "676 Rechnungen verifiziert")
    # unique_together: (checklist_type, year_month)

class ChecklistItemPause:
    checklist_type: str           # Welcher Checklisten-Typ
    item_id: str                  # Element-ID aus CHECKLIST_ITEMS (z.B. "pick_card")
    reason: TextField             # Warum pausiert?
    paused_until: DateField       # None = unbegrenzt, Datum = läuft ab
    created_at: DateTimeField     # auto_now_add
    # unique_together: (checklist_type, item_id)
    # is_active property: True wenn paused_until is None oder <= today
```

## URLs

```
/backups/checklist/<type>/                           GET  → Checkliste anzeigen
/backups/checklist/<type>/complete/                  POST → Abschließen
/backups/checklist/<type>/pause/<item_id>/           POST → Punkt pausieren
/backups/checklist/<type>/unpause/<item_id>/         POST → Pause aufheben
```

## Tests

30 Tests in `tests/test_operational_checklist.py`:
- `ChecklistItemPauseIsActiveTests` (6): past/today/future/None dates
- `OperationalChecklistCompletionTests` (3): not-completed, mark_complete, unique_together
- `OperationalChecklistViewTests` (6): GET, pause annotation, expired pause, invalid type, completed
- `ChecklistCompleteViewTests` (3): POST, GET redirect, already-completed
- `ChecklistPauseViewTests` (7): create, with date, update_or_create, invalid item, unpause, unpause nonexistent
- `ChecklistWidgetBuilderTests` (5): all pending, completed not shown, fully paused not shown, partially paused shown, expired pauses don't suppress

## Dateien

| Datei | Beschreibung |
|-------|-------------|
| `models/operational.py` | Beide Modelle |
| `models/__init__.py` | Export |
| `migrations/0041_add_operational_checklist.py` | Migration |
| `views/operational_views.py` | Views + `CHECKLIST_ITEMS` dict |
| `urls.py` | 4 URL-Patterns |
| `utils/dashboard_widgets.py` | `ChecklistWidgetBuilder` |
| `templates/my_practice/checklist.html` | Checklisten-Seite |
| `templates/includes/checklist_widget_content.html` | Widget |
| `templates/my_practice/dashboard.html` | Widget eingebunden |
| `admin.py` | Admin-Registrierung beider Modelle |
| `tests/test_operational_checklist.py` | 30 Tests |

## Related

- Root: [PROJECTS.md](../../../PROJECTS.md#p-012-operational-checklist-backup--recovery-automation)
- P-011: [Security Foundation](wip/P-011_SECURITY_FOUNDATION.md) — definiert die operativen Prozeduren, die diese Checklisten abbilden
