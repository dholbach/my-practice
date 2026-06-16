# P-001: Documentation Reorganization

**Status**: ✅ DONE
**Completed**: 2. Februar 2026
**Priority**: HIGH
**Effort**: ~6h

## Ziel

Klare Trennung zwischen Status, Dokumentation und Entwicklungsplanung.

## ✅ Completed Tasks

- [x] PROJECTS.md erstellen mit nummerierten Projekten
- [x] Redundante Dokumente konsolidieren
- [x] docs/guides/ erstellen
- [x] README auf <200 Zeilen kürzen
- [x] docs/projects/{todo,wip,done}/ Struktur
- [x] Projektbezogene Docs mit Nummern versehen
- [x] STATUS.md in PROJECTS.md integrieren
- [x] Archive mit Datumspräfixen organisieren
- [x] Completed improvements nach archive/completed/ verschoben
- [x] Copilot instructions aktualisiert

## Neue Struktur

```
docs/
├── README.md              # Index
├── FEATURES.md            # Was das System kann
├── CHANGELOG.md           # Was sich geändert hat
├── guides/                # User Guides
├── architecture/          # Wie es funktioniert
├── development/           # Development Setup
├── projects/              # 🆕 Projektbezogene Docs
│   ├── todo/             # P-002, P-003, etc.
│   ├── wip/              # P-001 (this file)
│   └── done/             # P-000, P-095-P-099
└── archive/               # Historisches
```

## Benefits

- Ein Ort pro Projekt (docs/projects/{status}/P-XXX_NAME.md)
- Cross-Referenzierung via Projektnummer
- Klare Status-Trennung (TODO/WIP/DONE)
- PROJECTS.md bleibt als Übersicht (Index)

## Related

- Root: [PROJECTS.md](../../../PROJECTS.md)
- Guides: [docs/guides/](../../guides/)
- Archive: [docs/archive/](../../archive/)
