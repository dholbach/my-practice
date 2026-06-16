# P-026: Klientendokument-Upload

**Status**: DONE (März 2026)

## Ziel

Dokumente (PDFs, Bilder) direkt an Klienten anheften — Behandlungsverträge, Aufnahmebögen,
Überweisungen und sonstiges. Upload direkt auf der Klienten-Detailseite ohne Seitenreload.

## Implementierung

### Modell `ClientDocument` (`models/client.py`)
- `DocumentType` (StrEnum): `contract`, `intake`, `referral`, `other`
- Felder: `client` (FK), `document_type`, `file`, `description`, `document_date`
- `client_document_upload_path()`: strukturierter Speicherpfad
  `clients/<code>/<year>/<type>-<date>-<slug>.<ext>` mit Kollisions-Handling
- Migration 0058

### Views (`views/client_views.py`)
- `client_document_upload` (POST) — validiert Datei + Typ, erstellt `ClientDocument`,
  gibt JSON mit Metadaten zurück (201)
- `client_document_delete` (POST) — löscht Datei + DB-Eintrag, gibt JSON zurück

### URLs
```
POST /clients/<pk>/documents/upload/    client_document_upload
POST /documents/<pk>/delete/            client_document_delete
```

### UI (`client_detail.html` + `client_detail.css`)
- Drag-and-Drop-Zone + Klick-zum-Auswählen (`<input type="file">`)
- Dateiname-Inferenz: erkennt führendes `YYYY-MM-DD` als Datum, Schlüsselwörter
  (`behandlungsvertrag`, `aufnahmebogen`, `überweisung`) als Typ, Rest als Beschreibung
- Formular erscheint nach Dateiauswahl (Typ, Beschreibung, Datum); Upload via `fetch()`
- Dokumentenliste wird in der Sidebar-Card angezeigt und per JS live aktualisiert
- Dark-Mode-kompatibel

### Tests
- `test_client_documents.py` — Upload, Löschen, Pfad-Kollision, ungültige Typen
