# P-020: Belegverwaltung (Betriebsausgaben)

**Status**: DONE (19. März 2026; Phase 2 ergänzt Mai 2026)
**Priority**: HIGH — Steuererklärung 2025 (Abgabe Ende April 2026)
**Effort**: ~4–6h (Phase 1) + ~4h (Phase 2)

---

## Ziel

Belege, Quittungen und Rechnungen für Betriebsausgaben direkt im System ablegen — verknüpft mit dem jeweiligen `CompanyExpense`-Eintrag. Kein Hin- und Herwechseln zwischen App und Dateimanager zur Steuerzeit.

---

## Problem / Motivation

Aktuell werden Belege als Dateien außerhalb der App gespeichert. Bei der Steuererklärung muss manuell sichergestellt werden, dass jede `CompanyExpense` einen Beleg hat — kein Überblick im System selbst.

---

## Design-Entscheidung: Filesystem vs. DB

**Gewählt: Filesystem-Speicherung, Dateiname/Pfad in DB**

| Ansatz | Vorteile | Nachteile |
|--------|----------|-----------|
| DB (BinaryField) | Kein Inkonsistenz-Risiko | DB wächst stark; Backups schwerer; PDFs nicht direkt zugänglich |
| Filesystem + Pfad in DB | Dateien direkt zugänglich; DB bleibt schlank; Backup via bestehendes Skript | Inkonsistenz möglich (Datei gelöscht, Pfad noch in DB) |

**Begründung**: Belege werden in der Praxis nie verschoben oder umbenannt — das Inkonsistenz-Risiko ist real, aber vernachlässigbar. Django's `FileField` (mit `upload_to`) handhabt dies sauber.

**Speicherpfad-Schema**:
```
media/taxes/<year>/<expense_id>_<original_filename>
```

Beispiel: `media/taxes/2025/42_rechnung_telekom.pdf`

---

## UX-Flow (Create)

```
[ Neue Ausgabe ]
  ├─ Titel / Beschreibung  ← Textfeld
  ├─ Betrag, Datum, Kategorie  ← bestehende Felder
  └─ Beleg  ← Drag-and-Drop Zone
               "Datei hierher ziehen oder klicken"
               → beim Speichern: umbenennen + in taxes/<year>/ ablegen
```

Datei wird **beim Speichern des Formulars** automatisch umbenannt, z.B. von "invoice24872482466.pdf" zu media/taxes/2025/dell_laptop.pdf und in das richtige Verzeichnis verschoben — kein separater Upload-Schritt.

## UX-Flow (Edit)

```
[ Ausgabe bearbeiten ]
  ├─ bestehende Felder (vorausgefüllt)
  └─ Beleg
       falls kein Beleg vorhanden:  ← Drag-and-Drop Zone (wie Create)
       falls Beleg vorhanden:       📎 rechnung_telekom.pdf  [Herunterladen] [Ersetzen]
```

„Ersetzen" zeigt die Drag-and-Drop Zone; alter Beleg wird beim Speichern gelöscht und durch neue Datei ersetzt.

## Scope (MVP)

### Muss
- [ ] `CompanyExpense.receipt` — `FileField(upload_to=..., blank=True, null=True)`
- [ ] Drag-and-Drop Zone in Create-Formular (`CompanyExpenseForm`)
- [ ] Drag-and-Drop Zone in Edit-Formular — zeigt vorhandenen Beleg + "Ersetzen"-Option
- [ ] Beleg-Download / -Anzeige auf der Ausgabenliste (Icon wenn vorhanden)
- [ ] Fehlende-Belege-Filter auf der Ausgabenliste (`receipt__isnull=True`) — für Steuer-Review
- [ ] Migration
- [ ] Tests

### Kann (spätere Phase)
- [ ] Beleg-Vorschau (PDF inline oder neues Tab)
- [ ] Ausdruck/Export: ZIP aller Belege eines Jahres (analog zu P-015 Steuer-PDF)
- [ ] Erweiterung auf Klienten-Dokumente (P-009): unterschriebene Verträge, Anamnesebögen, etc.

---

## Technische Details

### Model
```python
# models/financial.py
def expense_receipt_upload_path(instance, filename):
    year = instance.date.year if instance.date else "unknown"
    return f"taxes/{year}/{instance.pk}_{filename}"

class CompanyExpense(TimestampedModel):
    # ... existing fields ...
    receipt = models.FileField(
        upload_to=expense_receipt_upload_path,
        blank=True,
        null=True,
        verbose_name="Beleg",
    )
```

**Hinweis**: `upload_to`-Funktion benötigt `instance.pk` — beim ersten Speichern (Create) ist `pk` noch `None`. Lösung: entweder `post_save`-Signal + `save()` oder unscharfer Pfad mit Datum + Zufallsstring für neue Instanzen.

Alternative mit Datum statt PK (robuster für Create):
```python
def expense_receipt_upload_path(instance, filename):
    year = instance.date.year if instance.date else "unknown"
    ext = Path(filename).suffix
    slug = slugify(Path(filename).stem)[:40]
    return f"taxes/{year}/{slug}{ext}"
```

### Sicherheit
- Belege sind interne Buchhaltungsdokumente — keine öffentliche URL
- Django `MEDIA_ROOT` ist nicht öffentlich zugänglich (nur über Nginx mit Auth oder Django-View)
- Download-View muss `@login_required` sein

### Backup
- `media/` wird bereits durch `backup.sh` gesichert — kein zusätzlicher Aufwand
  (Media liegen unter `$PAYMENTS_DATA_DIR/media/`, außerhalb des Repos)

---

## Phase 2: Multi-Belege + Steuerstatus (ergänzt)

### Neue Features
- **Mehrere Belege pro Ausgabe**: `CompanyExpense.receipt` (FileField) ersetzt durch
  `ExpenseReceipt`-Modell (FK zu `CompanyExpense`, related_name `receipts`)
- **Drag-and-Drop Multi-Upload**: `name="receipts"`, `multiple` — beliebig viele Dateien
  gleichzeitig auswählbar
- **Einzelbeleg-Löschen**: `expense_receipt_delete`-View mit `PermissionDenied`-Check
- **`is_filed_in_tax_return`**: BooleanField auf `CompanyExpense` — "In SE eingetragen"
- **Steuerzusammenfassung**: SE-Spalte sortierbar (`?sort=se`), Bearbeitungslink mit
  `?next=`-Rücknavigation

### Migrations
- `0050_add_expense_tax_filed_field`: Fügt `is_filed_in_tax_return` hinzu
- `0051_add_expense_receipt_model`: Erstellt `ExpenseReceipt`-Tabelle, migriert
  vorhandene Einzelbelege, entfernt altes `receipt`-Feld

### Technische Anpassung: Nested-Form-Bug
Löschformulare dürfen nicht innerhalb des Hauptformulars liegen (Browser ignoriert
verschachtelte `<form>`-Tags). Lösung: Delete-Forms werden am Seitenende gerendert und
per inline JS (`replaceWith()`) in die korrekte visuelle Position verschoben.

---

## Abgrenzung zu P-009 (Client Documentation)

| P-020 | P-009 |
|-------|-------|
| Betriebsausgaben-Belege | Klienten-Dokumente |
| `ExpenseReceipt` (1:n) | Neue `ClientDocument`-Tabelle (oder ähnlich) |
| Steuer-/Buchhaltungskontext | Therapeutischer Kontext, Datenschutz-sensitiv |
| Keine Rollenprüfung nötig | Erfordert P-010 (Emergency Access, Rollen) |

P-020 kann unabhängig von P-009 und P-010 umgesetzt werden.
