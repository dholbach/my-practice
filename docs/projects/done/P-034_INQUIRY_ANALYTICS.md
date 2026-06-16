# P-034 — Anfragen-Analytics + Meilenstein-Dates

**Status**: DONE (April 2026)

## Ziel

Aussagekräftige Auswertungen für die Anfragen-Pipeline (`/inquiries/`) — Conversion-Funnel, Wartezeiten pro Stage, Quellen-Breakdown — sowie strukturierte Datum-Erfassung für jeden Meilenstein im Intake-Prozess.

## Umgesetzt

### Modell-Erweiterung (`ClientInquiry` — Migration 0070)

4 neue nullable DateFields:

| Feld | Bedeutung | Auto-Fill |
|---|---|---|
| `contacted_date` | Erstkontakt / Rückmeldung | Beim Wechsel auf Status CONTACTED |
| `intro_date` | Datum des Vorgesprächs | Beim Wechsel auf Status INTRO_MEETING |
| `intake_date` | Aufnahme gestartet | Beim Wechsel auf Status IN_INTAKE |
| `converted_date` | Als Klient:in aufgenommen | In `InquiryConvertView.post()` |

### Auto-Fill-Logik

`InquiryForm.save()` prüft beim Speichern: wenn der neue Status einem Meilenstein entspricht und das Datumsfeld noch leer ist, wird es auf `date.today()` gesetzt. Der Nutzer kann das Datum manuell überschreiben.

### Auswertungs-Panel auf `/inquiries/`

Einklappbare Leiste über der Tabelle, berechnet von `_build_inquiry_analytics()` in `inquiry_views.py`:

- **Pipeline-Funnel**: Anzahl pro Stage (Neu → Kontaktiert → Vorgespräch → Warteliste → Aufnahme → Aufgenommen), plus Anzahl geschlossener Anfragen
- **Ø Wartezeit pro Transition**: Tage zwischen den Meilensteinen (nur wenn Datumsdaten vorliegen, mit Stichprobengröße)
- **Quellen-Breakdown**: Anzahl + Prozentteil pro Kanal mit Balkendiagramm
- **Monats-Trend**: Anzahl Anfragen pro Monat, letzte 12 Monate (via Django `TruncMonth`)

### Formular

Neuer Fieldset „Meilensteine" in `inquiry_form.html` mit allen 4 Datumsfeldern (optional, mit Hinweis auf automatische Befüllung).

## Dateien

- `app/my_practice/models/inquiry.py` — 4 neue Felder
- `app/my_practice/migrations/0070_inquiry_milestone_dates.py`
- `app/my_practice/inquiry_forms.py` — Felder + Auto-Fill in `save()`
- `app/my_practice/views/inquiry_views.py` — `_build_inquiry_analytics()` + Kontext in `InquiryListView`
- `app/templates/my_practice/inquiry_form.html` — Meilenstein-Fieldset
- `app/templates/my_practice/inquiry_list.html` — Analytics-Panel
- `app/static/css/inquiry_list.css` — Analytics-Styles
