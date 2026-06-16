# P-014: Zahlungserinnerung per E-Mail

**Status**: TODO
**Priority**: MEDIUM
**Effort**: 3-4h
**Created**: 4. März 2026

---

## Problem

Offene Rechnungen bleiben manchmal länger unbezahlt, ohne dass der Klient daran erinnert wird. Aktuell gibt es keinen direkten Weg, eine Zahlungserinnerung zu senden — man muss die Rechnung manuell aufrufen und per Einzel-E-Mail schicken.

---

## Lösung

**"Zahlungserinnerung senden"**-Button auf der Klienten-Detailseite.

Sendet eine E-Mail mit allen offenen Rechnungen des Klienten (Status `draft` oder `sent`, nicht `paid` / `cancelled`):
- Rechnungsnummer, Datum, Betrag
- Gesamtbetrag aller offenen Rechnungen
- Praxis-Signatur

---

## Implementierung

### 1. View: `SendPaymentReminderView` (`email_views.py`)
- `GET /clients/<pk>/payment-reminder/` → Formular-Seite mit offenen Rechnungen + editierbarem E-Mail-Text (wie `SendInvoiceEmailView`)
- `POST` → E-Mail senden + Feedback-Nachricht
- Guards:
  - Keine offenen Rechnungen → Weiterleitung mit Hinweis
  - Kein `client.email` → Fehlermeldung
- Nutzt bestehende `EmailMessage`-Infrastruktur + `practice.email_signature`

### 2. E-Mail-Inhalt (Plain Text)
```
Betreff: Erinnerung: Offene Rechnung(en) – [Praxisname]

Sehr geehrte/r [Klient-Anrede oder Klient-Code],

hiermit möchte ich Sie an folgende offene Rechnung(en) erinnern:

  Nr.          Datum        Betrag
  INV-2026-01  01.01.2026   150,00 €
  INV-2026-05  15.02.2026   150,00 €

Gesamtbetrag offen: 300,00 €

[Bankverbindung aus Practice-Settings falls vorhanden]

[E-Mail-Signatur]
```

### 3. URL
```python
path("clients/<int:pk>/payment-reminder/", SendPaymentReminderView.as_view(), name="send_payment_reminder"),
```

### 4. Button auf `client_detail.html`
```html
{% if client.email and unpaid_invoices %}
<a href="{% url 'send_payment_reminder' client.pk %}" class="btn btn-secondary">
    📧 Zahlungserinnerung senden
</a>
{% endif %}
```

### 5. Template `my_practice/send_payment_reminder.html`
- Zeigt offene Rechnungen als Tabelle
- Editierbarer Betreff + E-Mail-Text (wie `send_invoice_email.html` / `InvoiceEmailForm`-Muster)
- "Jetzt senden" Button

---

## Offene Fragen

- [ ] Soll die Erinnerung im System protokolliert werden (Datum, wer gesendet hat)?
  → Wahrscheinlich sinnvoll; kann als `Invoice`-Notiz oder separates Modell
- [ ] Bankverbindung: aus `Practice`-Modell ziehen (`bank_iban` oder ähnliches Feld)?

## Acceptance Criteria

- [ ] Button auf Klienten-Detailseite sichtbar wenn: E-Mail vorhanden + offene Rechnungen
- [ ] Button deaktiviert/ausgeblendet wenn: keine E-Mail oder keine offenen Rechnungen
- [ ] E-Mail enthält: alle offenen Rechnungen (Nr., Datum, Betrag), Gesamt, Signatur
- [ ] Erfolgsmeldung nach dem Senden
- [ ] Tests für View (kein E-Mail, keine offenen Rechnungen, erfolgreicher Versand)
