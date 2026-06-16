# P-018: Aufnahmeprozess-Workflow

**Status**: DONE (März 2026)

## Ziel

Strukturierter Onboarding-Stepper auf der Klienten-Detailseite: trackt die Schritte des
Aufnahmeprozesses (Aufnahmebogen, Vertrag, Anamnesebogen) mit Datumsstempel und ermöglicht
Versand per E-Mail direkt aus der Anwendung.

## Implementierung

### Modell `Client` — neue Felder (Migration 0045)
- `intake_sent_date` — Datum Aufnahmebogen ausgehändigt
- `contract_signed_date` — Datum Behandlungsvertrag unterzeichnet
- `questionnaire_sent_date` — Datum Anamnesebogen versendet
- `onboarding_complete_date` — Datum Aufnahmeprozess abgeschlossen

### View (`views/client_views.py`)
- `client_onboarding_step(request, pk)` (POST) — markiert oder setzt einzelnen Schritt zurück
  über `?step=intake|contract|questionnaire|complete` + `?reset=1`

### E-Mail-Views (`views/email_views.py`)
- `SendQuestionnaireEmailView` — versendet Anamnesebogen (.docx) als Anhang;
  setzt `questionnaire_sent_date` nach Versand
- `SendContractEmailView` — generiert Behandlungsvertrag-PDF live und versendet als Anhang;
  nutzt `generate_contract_pdf_bytes()` aus `api_views`

### URL
```
POST /clients/<pk>/onboarding-step/           client_onboarding_step
GET/POST /clients/<pk>/send-questionnaire/    send_questionnaire_email
GET/POST /clients/<pk>/send-contract/         send_contract_email
```

### UI (`client_detail.html` Sidebar)
- Aufklappbarer Onboarding-Stepper mit 4 Schritten
- Jeder Schritt zeigt Datum (wenn erledigt) oder Hinweis + Aktions-Buttons
- „Rückgängig"-Links zum Zurücksetzen einzelner Schritte
- Stepper bleibt offen solange `onboarding_complete_date` nicht gesetzt
