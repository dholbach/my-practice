# P-013: Workflow-Orientierte Dashboard-Ansichten

**Status**: ✅ DONE — Alle 3 Phasen abgeschlossen (4. März 2026)
**Priority**: MEDIUM
**Effort**: ~10h gesamt (Phase 1: ~6h, commit `9e7587b`; Phase 2: ~2h, commit `f5f48a2`; Phase 3: ~2h, commit `904809c`)
**Completed**: 4. März 2026

---

## Phase 1: Kalender-Ereignis-Warteschlange ✅ DONE (3. März 2026)

### Was wurde gebaut

**`PendingCalendarEvent` Modell** (Migration `0042`):
- Persistente Warteschlange für Google-Kalender-Ereignisse
- Idempotent via `google_event_id` (unique constraint)
- Statusfluss: `pending` → `imported` | `skipped` | `cancelled`
- Indizes für Practice+Status und Client+Datum

**Management Command `fetch_calendar_events`**:
- Inkrementeller Abruf (2h Overlap-Fenster, kein Neustart nötig)
- Erkennt abgesagte Termine (nicht mehr in Google → Status `cancelled`)
- `--dry-run` und `--days` Parameter
- Systemd-Timer läuft alle 4h (`payments-fetch-calendar-events.timer` ✅ aktiv)

**Genehmigungs-Warteschlange** (`/calendar/genehmigen/`):
- Termine gruppiert nach Klient × Abrechnungsmonat
- Verhindert versehentliches Mischen mehrerer Monate auf eine Rechnung
- JS-basiertes Import/Skip ohne Seitenneuladen

**Rechnungs-Preflight-Check** (auf Rechnungsdetailseite):
- `CalendarPreflightChecker`: Fuzzy-Matching (±2 Tage, ±5 Min)
- Status je Position: `confirmed` / `moved` / `cancelled` / `unmatched`
- Zeigt kalender-Ereignisse die nicht auf der Rechnung stehen
- Nur für Entwurf/Gesendet-Rechnungen aktiv (nicht-blockierend)

**Dashboard-Widget**: Badge zeigt ausstehende Termine mit Link zur Warteschlange

---

## Problem (ursprünglich)

Die aktuelle UI ist daten-zentriert (Rechnungen, Klienten, Analysen) statt workflow-zentriert.
Typische Arbeitsabläufe erfordern Navigation über mehrere Seiten:
- Monatlich: Rechnungen schreiben (Calendar Import → Invoice Creation → Send Email)
- Quartalsweise: Steuervorauszahlungen + Steuerübersicht
- Ad-hoc: Kapazitätsprüfung (Sind Stunden runter? Sind Einnahmen runter? Was ist zu tun?)

---

## Ziel

Workflow-basierte Ansichten, die häufige Arbeitsabläufe unterstützen:

### 1. Monatlicher Rechnungs-Workflow
**Frequenz**: 1-2x pro Monat
**Schritte**:
1. Kalender-Events importieren
2. Fehlende InvoiceItems prüfen
3. Rechnungen erstellen (Draft → Sent)
4. E-Mails versenden
5. Zahlungseingänge verfolgen

**Ansicht**: Unified "Rechnungsworkflow" Seite
- Badge: "X Events zum Importieren"
- Badge: "Y Draft Invoices"
- Badge: "Z Unbezahlte Rechnungen"
- One-Click Actions für jeden Schritt

### 2. Quartalsweise Steuer-Workflow
**Frequenz**: 4x pro Jahr
**Schritte**:
1. Steuerübersicht für Quartal generieren
2. Vorauszahlung berechnen
3. Withdrawal erfassen
4. Bestätigung/Quittung speichern

**Ansicht**: "Steuer-Quartal" Seite
- Automatische Berechnung basierend auf Q1-Q4
- Direkter Link zu Withdrawal-Formular
- Historie vergangener Vorauszahlungen

### 3. Kapazitäts-Monitoring (Always-On)
**Frequenz**: Ad-hoc
**Ziel**: Frühwarnung bei rückläufigen Zahlen

**Features**:
- **Minimum-Stunden definieren** (z.B. 60h/Monat)
- **Minimum-Einnahmen definieren** (z.B. 4000€/Monat)
- **Warnings**:
  - "⚠️ Stunden unter Minimum (45h < 60h)"
  - "⚠️ Einnahmen unter Minimum (3200€ < 4000€)"
- **Trends**: 3-Monats-Durchschnitt vs. aktuelle Zahlen
- **Empfehlungen**: "3 neue Klienten nötig" oder "2 zusätzliche Stunden/Woche"

**Ansicht**: Dashboard-Widget oder eigene "Kapazitäts-Check" Seite

---

## Design-Prinzipien

1. **Action-First**: Jede Ansicht hat klare Next Actions
2. **Context-Aware**: Zeigt nur relevante Info für aktuellen Workflow
3. **Progressive Disclosure**: Details auf Demand, nicht alles auf einmal
4. **Smart Defaults**: Automatische Berechnungen, Minimum Clicks

---

## Implementation Plan

### Phase 1: Kalender-Ereignis-Warteschlange ✅ DONE (3. März 2026, ~6h)
- [x] `PendingCalendarEvent` Modell + Migration 0042
- [x] `fetch_calendar_events` Management Command + Systemd-Timer (4h)
- [x] Genehmigungs-Warteschlange gruppiert nach Klient × Monat
- [x] Rechnungs-Preflight-Check mit Fuzzy-Matching
- [x] Dashboard-Widget mit Badge
- [x] Admin-Integration

### Phase 2: Steuer-Workflow ✅ DONE (3. März 2026, ~2h, commit `f5f48a2`)
- [x] `tax_quarter_overview` View + `_quarter_date_range()` Helper (`/reports/steuer-quartal/`)
- [x] Q1-Q4 Tabelle: Umsatz, absetzbare Ausgaben, Nettogewinn, Vorauszahlungen, Status
- [x] `needs_attention`-Flag: Quartal hat Umsatz aber keine Vorauszahlung
- [x] `TaxQuarterWidgetBuilder` Dashboard-Widget mit ⚠️-Badge (Q >50% vergangen, keine Zahlung)
- [x] `WithdrawalCreateView.get_initial()`: `?category=tax` pre-fills Formular
- [x] Templates: `tax_quarter_overview.html` + `includes/tax_quarter_widget_content.html`

### Phase 3: Kapazitäts-Monitoring ✅ DONE (4. März 2026, ~2h, commit `904809c`)
- [x] `Practice.monthly_target_hours` + `Practice.monthly_target_revenue` Felder (migration 0043)
- [x] `CapacityMonitoringWidgetBuilder`: 3-Monats-Trend, Stunden + Umsatz vs. Ziel
- [x] Warnung bei <80 % des Monatsziels mit Badge-System
- [x] `includes/capacity_monitoring_widget_content.html` Template (Progress Bars)
- [x] Fieldset "Kapazitäts-Monitoring" in PracticeAdmin
- [x] Dashboard-Widget (nur sichtbar wenn Ziele konfiguriert)
- [x] Session Import Widget aus Dashboard entfernt (toter P-003-Widget)
- [x] 📅 Kalender-Link aus Top-Nav in Admin-Dropdown verschoben

---

## Benefits

- **Zeitersparnis**: Weniger Clicks, direktere Workflows
- **Proaktiv**: Warnings statt reaktives Handeln
- **Clarity**: Klare Next Actions, keine Ratlosigkeit
- **Confidence**: Zahlen immer im Blick, rechtzeitige Maßnahmen

---

## Referenzen

- User Feedback (15. Feb 2026): workflow-zentrierte Ansichten gewünscht
- Related: P-003 (Workflow Dashboard) - erste Schritte in diese Richtung
- Related: P-004 (Analytics Consolidation) - bessere Info-Gruppierung

---

## Notes

**Future Consideration**: Integration mit externen Tools
- Lexoffice API für automatische Steuerübermittlung?
- Google Calendar Auto-Sync (nicht nur Import)?
- Erinnerungs-E-Mails für Klienten (Zahlungserinnerung)?

Diese Features sollten aber erst nach P-013 Core-Implementation evaluiert werden.
