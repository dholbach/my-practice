# P-031: Client Inquiry / Lead Tracking

**Status: DONE** (2026-03-30)

## Ziel
Modul zur Aufnahme, zum Tracking und zur direkten Bearbeitung von Erstkontakten,
Klientenanfragen ("Leads") und Wartelisten-Interessenten — vollständig
praxis-gescoped und nahtlos in den bestehenden Klienten-Workflow integriert.

## Implementierung

### Modell (`models/inquiry.py`)
- `ClientInquiry(TimestampedModel)` — praxis-gescoped via `PracticeScopedManager`
- `InquirySource` (StrEnum): `google_ads`, `google_organic`, `website`, `referral`,
  `directory`, `its_complicated`, `network`, `other`
- `InquiryStatus` (StrEnum): `new`, `contacted`, `intro_meeting`, `waitlist`,
  `in_intake`, `converted`, `declined`, `unreachable`, `not_suitable`
  - `not_suitable` ("Kein Match") — unqualified leads / expectation mismatch; terminal state
- Felder: `full_name`, `email`, `phone`, `source`, `status`, `inquiry_date` (default: today),
  `notes`, `converted_client` (FK → Client, optional)
- `ClientInquiryQuerySet.open()` — filtert alle nicht-abgeschlossenen Einträge
- `MarketingPeriod(TimestampedModel)` — praxis-gescoped Marketingzeitraum
  - Felder: `start_date`, `end_date` (optional), `description` (Freitext)
  - `is_active()` — prüft ob heute im Zeitraum liegt
  - Ziel: Anfragen-Quellen mit Marketingaktivitäten korrelieren (Stats geplant)

### Formulare (`inquiry_forms.py`)
- `InquiryForm` — CRUD für Anfragen-Felder, nutzt `StyledFormMixin` und `DateFormField`
- `InquiryConvertForm` — Aufnahme einer Anfrage als Klient:in:
  `client_code`, `default_hourly_rate`, `first_seen_date`

### Views (`views/inquiry_views.py`)
- `InquiryListView` — gefiltert nach Status / Source (GET-Parameter)
- `InquiryCreateView` — praxis-gescoped, success message
- `InquiryUpdateView` — zeigt "In Klient konvertieren"-Button wenn noch nicht konvertiert
- `InquiryDeleteView` — Bestätigungsseite
- `InquiryConvertView` (View) — GET: Bestätigungsformular; POST: erstellt `Client`,
  setzt `inquiry.status = CONVERTED`, verlinkt `inquiry.converted_client`

### URLs
```
/inquiries/                 inquiry_list
/inquiries/new/             inquiry_create
/inquiries/<pk>/edit/       inquiry_update
/inquiries/<pk>/delete/     inquiry_delete
/inquiries/<pk>/convert/    inquiry_convert
```

### Templates
- `inquiry_list.html` — Tabelle mit Status-Badges, Quell-Badge, Filter-Dropdowns
- `inquiry_form.html` — Erstell- / Bearbeitungsformular
- `inquiry_confirm_delete.html` — Lösch-Bestätigung
- `inquiry_convert_confirm.html` — Aufnahme-Formular (client_code, rate, Datum)

### CSS (`static/css/inquiry_list.css`)
Badge-Styles für `status-*` und `source-*` Klassen; Dark-Mode-kompatibel.
`th-sensitive` — 🔒-Icon via `::after` auf Spaltenköpfen mit personenbezogenen Daten (Name, Kontakt).

### Admin (`admin.py`)
- `ClientInquiryAdmin` — list_display mit Status-Badge, Search, Filter
- `MarketingPeriodAdmin` — `is_active_badge` (boolean display), Sort by `-start_date`

### Inquiry List — UX-Details
- Aktive Marketingzeiträume als Badge-Leiste oberhalb der Filterspalte
  ("+Hinzufügen"-Link → Admin; leer: "Marketing-Zeitraum erfassen"-Hint)
- Name- und Kontakt-Spaltenköpfe haben `title="Personenbezogene Daten"` + 🔒-Icon

### Navigation
Nav-Link "Anfragen" in `base.html`; Anfragen-Block in `client_detail.html`
(zeigt offene Anfragen des Klienten).

### Migrationen
- `0060_add_client_inquiry.py` — fügt `ClientInquiry`-Tabelle hinzu
- `0061_add_client_inquiry.py` — Folge-Migration (Practice-Relation)
- `0063_alter_clientinquiry_source_marketingperiod.py` — `its_complicated`-Quelle + `MarketingPeriod`-Tabelle
- `0064_alter_clientinquiry_status.py` — `not_suitable`-Status

### Tests (`tests/test_inquiry.py`)
Volle CRUD-Coverage: Erstellen, Bearbeiten, Löschen, Konvertieren,
Praxis-Scoping, Redirect/Status-Prüfungen. 22 Anfragen-Tests grün.

## Begleitende Änderungen (gleiche Session)
- `config/exception_reporter.py` + `tests/test_pii_reporter.py`: PII-Filter für
  Django 500-Fehlerseiten (schwärzt E-Mail, Name, IBAN in Tracebacks)
- Migration `0062`: SessionLog `content` / `therapist_reflection` Help-Text aktualisiert
- `test_admin.py`: Management-Form-Präfix-Fix (`documents-` statt `clientdocument_set-`)
