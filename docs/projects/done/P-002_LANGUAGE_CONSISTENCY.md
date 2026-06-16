# P-002: Sprachkonsistenz (UI auf Deutsch)

**Status**: ✅ DONE
**Completed**: 2. Februar 2026 (Hauptphase) + 15. Februar 2026 (Nachbesserungen)
**Priority**: MEDIUM
**Effort**: ~5h (3 Phasen + Nachbesserungen)

## Problem

Mix aus Deutsch/Englisch in der UI:
- "Google Calendar Import", "Dashboard", "Revenue Report"
- vs. "Rechnungen", "Klienten", "Entnahmen"
- Model verbose_names: "Client Code", "Email", "Invoice Number"
- STATUS_CHOICES: "Draft / Entwurf" (bilingual format)

## Ziel

- Alle UI-Elemente auf Deutsch (außer technische API-Begriffe)
- Rechnungen bleiben bilingual (title_de/title_en)
- Django Admin Interface auf Deutsch
- Konsistente Model-Labels

## ✅ Completed Tasks

- [x] Audit aller page_title Blocks (8 Templates)
- [x] Button-Labels konvertieren (View → Ansehen, Cancel → Storniert)
- [x] Navigationsmenü standardisieren (Dashboard → Übersicht, Analytics → Auswertungen)
- [x] Headings aktualisiert (Holiday Times → Urlaubszeiten, etc.)
- [x] Model verbose_names (7 Models)
- [x] STATUS_CHOICES (bilingual → German only)

## Results

**3 Commits**, **18 Dateien geändert**:

### Phase 1 - Templates: Page Titles & Navigation (Commit 960ece5)
**8 Templates**:
- base.html: Navigation German
- dashboard.html: Übersicht
- analytics.html: Auswertungen
- practice_analysis.html: Praxisanalyse
- revenue_report.html: Umsatzbericht
- send_invoice_email.html: Rechnung versenden
- todo_list.html: Aufgaben
- calendar_import.html: Kalender Import

### Phase 2 - Templates: Button Labels & Headings (Commit 78f7f3e)
**3 Templates**:
- invoice_list.html: View → Ansehen
- calendar_import.html: Cancelled → Storniert
- practice_analysis.html: 4 English headings → German

### Phase 3 - Models: verbose_names & STATUS_CHOICES (Commit 1356497)
**7 Models** (48 insertions/deletions):

**Invoice Model**:
- STATUS_CHOICES: "Draft / Entwurf" → "Entwurf"
- STATUS_CHOICES: "Sent / Gesendet" → "Gesendet"
- STATUS_CHOICES: "Paid / Bezahlt" → "Bezahlt"
- STATUS_CHOICES: "Cancelled / Storniert" → "Storniert"
- Fields: "Invoice Number" → "Rechnungsnummer", "Client" → "Klient"
- "Subtotal" → "Zwischensumme", "Tax Rate (%)" → "Steuersatz (%)"
- "Total" → "Gesamtbetrag", "Notes" → "Notizen"
- Meta: "Invoice / Rechnung" → "Rechnung"

**InvoiceItem Model**:
- "Service Type" → "Leistungsart", "Session Date" → "Sitzungsdatum"
- "Duration (minutes)" → "Dauer (Minuten)", "Quantity" → "Menge"
- "Rate" → "Satz", "Total" → "Gesamt"
- Meta: "Invoice Item" → "Rechnungsposition"

**Client Model**:
- "Client Code" → "Klientenkürzel"
- "Full Name" → "Vollständiger Name", "Date of Birth" → "Geburtsdatum"
- "Email" → "E-Mail", "Phone" → "Telefon", "Address" → "Adresse"
- "Hourly Rate (60 min)" → "Stundensatz (60 Min)"
- "Hourly Rate (90 min)" → "Stundensatz (90 Min)"
- "Cancellation Fee" → "Ausfall-Gebühr"
- "Preferred Language" → "Bevorzugte Sprache"
- "Email Salutation" → "E-Mail Anrede"
- "Active" → "Aktiv", "Online Client" → "Online Klient"
- Meta: "Client" → "Klient"

**Practice Model**:
- "Email From Name" → "E-Mail Absendername"
- "Email Subject (English)" → "E-Mail Betreff (English)"
- "Email Body (English)" → "E-Mail Text (English)"
- "Email Signature" → "E-Mail Signatur"

**ServiceType Model**:
- "Default Duration (minutes)" → "Standarddauer (Minuten)"
- Meta: "Service Type" → "Leistungsart"

**ClientTag Model**:
- Meta: "Client Tag" → "Klient-Tag"

**GoogleCalendarToken Model**:
- Meta: "Google Calendar Token" → "Google Kalender Token"
- __str__: "Active/Inactive" → "Aktiv/Inaktiv"

**PracticeTodo Model**:
- Meta: "Practice TODO" → "Aufgabe"

## Principle

**Deutsch für UI, bilingual für Geschäftsdokumente**
- Admin Interface: Pure German
- Invoice PDFs: Bilingual (title_de/title_en)
- STATUS_CHOICES: German only (admin shows German)

## Examples

**Templates (Vorher → Nachher)**:
- "Google Calendar Import" → "Kalender Import"
- "Dashboard" → "Übersicht"
- "Revenue Report" → "Umsatzbericht"

**Models (Vorher → Nachher)**:
- "Draft / Entwurf" → "Entwurf"
- "Client Code" → "Klientenkürzel"
- "Email From Name" → "E-Mail Absendername"

## Impact

- Django Admin Interface vollständig auf Deutsch
- Konsistente Beschriftungen in Tabellen/Formularen
- Keine doppelten Bezeichnungen mehr ("Draft / Entwurf")
- Bessere UX für deutschsprachige Nutzer

## Related

- Root: [PROJECTS.md](../../../PROJECTS.md#p-002-language-consistency)
