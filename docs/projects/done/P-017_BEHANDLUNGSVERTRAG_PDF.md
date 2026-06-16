# P-017: Behandlungsvertrag PDF

**Status**: DONE (März 2026)

## Ziel

Automatische Generierung eines vorausgefüllten Behandlungsvertrags als PDF — mit ausfüllbaren
Formularfeldern, bilingual (DE/EN), inklusive DSGVO-Abschnitt.

## Implementierung

### Template (`templates/my_practice/behandlungsvertrag_pdf.html`)
- Vollständiger Behandlungsvertrag DE/EN mit `{{ lang }}`-Schalter
- §§ 1–9: Vertragsgegenstand, Honorar, Datenschutz (DSGVO), Fernberatung, Schweigepflicht usw.
- Praxisdaten (Logo, Adresse) und Klientendaten vorausgefüllt
- WeasyPrint-kompatibles Layout mit fixen Header-Styles

### View / Helper (`views/api_views.py`)
- `contract_pdf(request, pk)` — liefert PDF als Download
- `generate_contract_pdf_bytes(client, practice, lang)` — gemeinsamer Helper,
  auch von `SendContractEmailView` genutzt
- `add_contract_form_fields(pdf_bytes)` (`utils/contract_form.py`) — fügt
  ausfüllbare Felder per PyMuPDF/pikepdf hinzu

### URL
```
GET /clients/<pk>/contract-pdf/    contract_pdf
```

### Integration
- Button auf Klienten-Detailseite → direkter Download
- E-Mail-Versand über `SendContractEmailView` (→ P-018)
