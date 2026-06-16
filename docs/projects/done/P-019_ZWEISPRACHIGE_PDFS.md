# P-019: Zweisprachige PDFs (Bilingual Invoices)

**Status**: DONE (März 2026)

## Ziel

Rechnungs-PDFs werden bilingual (DE/EN) generiert — Klient:innen mit `language=en`
erhalten englische Rechnungen; alle anderen deutsch. Beide Templates teilen dasselbe
visuelle Layout.

## Implementierung

### Modell
- `InvoiceItem.title_de` + `title_en` — separate Bezeichnungen pro Sprache
- `ServiceType.title_de` + `title_en` — globale Bezeichnungen für Dienstleistungstypen
- `Client.language` (`de` | `en`) steuert die PDF-Sprache

### Templates
- `invoice_pdf_de.html` — deutsches Invoice-Template (WeasyPrint)
- `invoice_pdf_en.html` — englisches Invoice-Template
- Gemeinsame Basis: `invoice_pdf_base.css` für identisches Layout

### View (`views/api_views.py`)
- `invoice_pdf(request, pk)` wählt Template nach `client.language`
- `_render_invoice_pdf_bytes()` als gemeinsamer Helper für Einzel- und Batch-Download

### Batch-Download (`invoice_batch_download`)
- Generiert ZIP mit PDFs für mehrere Rechnungen gleichzeitig
- Jede Rechnung nutzt die Sprache des Klienten

### Praxis-Konfiguration
- `Practice.is_kleinunternehmer` — schaltet zwischen §19 UStG und §4 Nr.14 UStG um
- Rechnungstexte und MwSt.-Hinweise werden entsprechend gerendert
