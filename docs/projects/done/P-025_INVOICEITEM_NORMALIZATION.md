# P-025: InvoiceItem-Normalisierung

**Status**: DONE (März 2026)

## Ziel

Sitzungsdaten aus `InvoiceItem` in ein separates `Session`-Modell auslagern.
Vorher wurden `session_date`, `duration` und `session_type` direkt auf `InvoiceItem`
gespeichert — vermischte Zuständigkeiten (Rechnungszeile vs. klinische Sitzungsdaten).

## Implementierung

### Neues Modell `Session` (`models/session.py`)
- Felder: `client`, `session_date`, `duration`, `session_type`, `practice`
- Getrennte Zuständigkeit: eine Sitzung existiert unabhängig von der Rechnung

### `InvoiceItem` (geändert)
- `session` FK → `Session` (nullable, `on_delete=SET_NULL`)
- `session_date`, `duration`, `session_type` nicht mehr direkt auf InvoiceItem
- Deduplizierung: `get_or_create` verhindert Doppel-Sessions bei gleichem Client + Datum + Dauer

### Formulare (`invoice_forms.py`)
- `InvoiceItemForm.session_date` und `duration` als virtuelle Felder beibehalten
  (UX bleibt identisch)
- Beim Speichern im View: `Session.objects.get_or_create(client, session_date, duration, ...)`
  → verknüpft neuen oder bestehenden Session-Datensatz

### Views (`invoice_views.py`)
- `InvoiceCreateView` + `InvoiceEditView` aktualisiert: erstellen/aktualisieren `Session`
  beim Speichern des Formsets
- Kalender-Import (`calendar_views.py`): Duplikaterkennung auf `Session` umgestellt

### Migration
- Migrations 0055–0057: `Session`-Tabelle anlegen, Daten rückwärtig befüllen (RunPython),
  Felder auf InvoiceItem entfernen

## Ergebnis
- Saubere Trennung: `InvoiceItem` = Rechnungszeile; `Session` = klinischer Termin
- Basis für zukünftige Session-Auswertungen unabhängig von Rechnungen
- Kalenderimport und Duplikaterkennung weiterhin funktionsfähig
