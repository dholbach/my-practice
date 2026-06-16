# Google Calendar Integration - User Guide

**Status**: ✅ Phase 1-5 Complete
**Last Updated**: 31. Januar 2026

---

## Übersicht

Import von Therapie-Sessions aus Google Calendar direkt in das Rechnungssystem. Erstellt automatisch InvoiceItems für alle geplanten Sessions.

---

## Features

### ✅ Phase 1-5 Complete

**OAuth2 Integration**:
- Sichere Authentifizierung mit Google
- Filter auf "Praxis" Calendar
- Token auto-refresh (proactive 5-min expiry check)
- API pagination (>250 events support)

**Event Parser**:
- Client Matching via Initialen im Event-Titel
- Cancel Detection (durchgestrichene Events)
- Farb-codierte Status-Anzeige
- Duration-based Service Type Mapping

**Approval UI**:
- Manuelle Korrekturen (Client/Service Type ändern)
- Smart Auto-Selection für ready Events
- Duplicate Detection mit Visual Indicators
- Status Badges mit Tooltips
- Bulk Actions: "Import selected"

**InvoiceItem Creation**:
- Erstellt Items aus approved Events
- Duplicate Prevention (prüft existierende Items)
- Free Vorgespräch Handling (0€ rate)
- First Seen Date Auto-Tracking
- Single Draft Invoice per Client
- Comprehensive Error Reporting

**Production Polish**:
- Session Storage Event Caching (30-min cache)
- Performance Optimizations
- Error Handling

---

## Setup

### 1. Google Cloud Console
1. Projekt erstellen: [console.cloud.google.com](https://console.cloud.google.com)
2. APIs aktivieren: **Google Calendar API**
3. OAuth 2.0 Client ID erstellen:
   - Application Type: **Web Application**
   - Authorized Redirect URIs: `http://localhost:8000/calendar/oauth2callback/`

### 2. Credentials Konfigurieren
```bash
# .env Datei
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
```

### 3. Erste Nutzung
1. **Calendar Import** im Hauptmenü öffnen
2. **"Mit Google verbinden"** klicken
3. Google Account auswählen und Berechtigungen erteilen
4. Automatische Weiterleitung zurück zur App

---

## Workflow

### 1. Events Abrufen
**Navigation**: Hauptmenü → **Calendar Import**

**Event Fetching**:
- Zeigt Events von HEUTE bis +365 Tage
- Filtert auf "Praxis" Calendar
- Session Caching (30 Minuten)

**Status Badges**:
- 🟢 **Ready**: Client gefunden, Service Type gemappt, keine Duplikate
- 🟡 **Needs Attention**: Client unklar oder Service Type fehlt
- 🔴 **Duplicate**: Bereits in InvoiceItems vorhanden
- ⚫ **Cancelled**: Event durchgestrichen

### 2. Events Überprüfen & Korrigieren

**Auto-Matching**:
- Parser sucht Initialen im Event-Titel (z.B. "AB" → "Müller, Anna (AB)")
- Duration → Service Type Mapping:
  - 60min → "Sitzung (60min)"
  - 90min → "Sitzung (90min)"
  - 15min → "Check-in"
  - Default → "Sitzung (60min)"

**Manuelle Korrekturen**:
- Dropdown: Client auswählen (falls Auto-Match fehlschlägt)
- Dropdown: Service Type ändern (falls Standard nicht passt)
- Changes werden sofort gespeichert (Session Storage)

**Smart Selection**:
- "Select Ready" Button: Wählt alle 🟢 Ready Events
- Spart Zeit bei Bulk-Import

### 3. Import Durchführen

**"Import Selected" Button**:
- Verarbeitet alle ausgewählten Events
- Erstellt InvoiceItems für jeden Client
- Fügt Items zu Draft Invoice hinzu (oder erstellt neue Draft)

**Duplicate Prevention**:
- Prüft existierende InvoiceItems (gleicher Tag + Client)
- Zeigt 🔴 Duplicate Badge
- Kann nicht importiert werden (checkbox disabled)

**Success Feedback**:
- Zeigt Anzahl erfolgreich importierter Sessions
- Listet Clients auf
- Link zu Invoice Draft

---

## Special Cases

### Vorgespräch (Initial Consultation)
**Erkennung**: "Vorgespräch" oder "Erstgespräch" im Event-Titel

**Automatische Behandlung**:
- Service Type: "Sitzung (60min)"
- **Rate: 0€** (kostenlos)
- First Seen Date: Automatisch gesetzt

### Group Sessions
**Event-Titel Format**: Muss Initialen enthalten (z.B. "Gruppe - AB, CD, EF")

**Handling**:
- Jeder Client bekommt separates InvoiceItem
- Service Type: Manuell als "Gruppensitzung" wählen
- Duration: Wie im Event angegeben

### Cancelled Events
**Anzeige**: ⚫ Cancelled Badge

**Handling**:
- Checkbox disabled (kann nicht importiert werden)
- Bleibt in Liste für Übersicht
- Optional: Manuell als "Ausfall" Invoice erstellen

---

## Technische Details

### Event Parser Logic
```python
# Duration → Service Type Mapping
duration_map = {
    60: "therapy_60",     # Sitzung (60min)
    90: "therapy_90",     # Sitzung (90min)
    15: "check_in",       # Check-in
    120: "therapy_120",   # Sitzung (120min)
}
```

### Client Matching
```python
# 1. Sucht Initialen in Event-Titel
# 2. Matched gegen Client.client_code
# 3. Falls mehrere Matches: Zeigt alle zur Auswahl
```

### Duplicate Detection
```python
# Prüft InvoiceItem mit:
# - Gleichem Datum (session_date)
# - Gleichem Client
# - ±5 Minuten Duration Variance (erlaubt kleine Abweichungen)
```

### Token Management
- OAuth Token wird in Session gespeichert
- Proactive Refresh bei <5 Minuten verbleibender Gültigkeit
- Automatische Re-Authentifizierung falls Token expired

---

## Dateien

### Backend
```
app/my_practice/
├── views/calendar_views.py        # OAuth + Import Views
├── utils/google_calendar.py       # Event Parser
├── forms.py                       # CalendarImportForm
└── urls.py                        # /calendar/* routes

app/config/
└── settings.py                    # GOOGLE_CLIENT_ID/SECRET
```

### Frontend
```
templates/my_practice/
└── calendar_import.html           # Import UI

static/
├── css/calendar_import.css        # Styling
└── js/calendar_import.js          # AJAX + Interactions
```

### Tests
```
app/my_practice/tests/
├── test_google_calendar.py        # Event Parser Tests
└── test_calendar_views.py         # Integration Tests
```

---

## Troubleshooting

### "Invalid Grant" Error
**Ursache**: OAuth Token expired

**Lösung**: Button "Mit Google verbinden" erneut klicken

### "No Events Found"
**Mögliche Ursachen**:
- Falscher Calendar Name (muss "Praxis" heißen)
- Keine Events in nächsten 365 Tagen
- Calendar nicht freigegeben

**Lösung**: Google Calendar prüfen, ggf. Calendar Name anpassen

### Client Nicht Gefunden
**Ursache**: Initialen im Event-Titel fehlen oder falsch

**Lösung**:
- Dropdown: Client manuell auswählen
- Oder: Event-Titel in Google Calendar korrigieren

### Duplicate Detected (False Positive)
**Ursache**: ±5min Variance Detection zu streng

**Lösung**:
- Existierendes Item in Invoice prüfen
- Falls wirklich Duplikat: Ignorieren
- Falls false positive: Existierendes Item löschen, erneut importieren

---

## Best Practices

1. **Regelmäßiger Import**: Wöchentlich oder nach Terminplanung
2. **Event-Titel Konsistenz**: Immer Initialen verwenden (z.B. "AB - Therapie")
3. **Calendar Name**: "Praxis" beibehalten für automatische Filterung
4. **Vorgespräch Kennzeichnung**: "Vorgespräch" im Titel für 0€ Handling
5. **Draft Invoice Prüfen**: Nach Import immer Draft Invoice kontrollieren

---

## Zukünftige Erweiterungen (Nice to Have)

- Bi-directional Sync (App → Google Calendar)
- Automatic Reminder Emails
- Recurring Appointment Templates
- Multi-Calendar Support
- Automatic Cancellation Handling (creates "Ausfall" invoice)
