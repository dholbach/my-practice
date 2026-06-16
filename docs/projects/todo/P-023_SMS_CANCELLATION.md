# P-023: SMS Sending via seven.io

**Status**: TODO  
**Priority**: Medium  
**Estimated effort**: ~4h  
**Created**: March 2026

---

## Goal

SMS sending from the web interface — primarily for cancellations (complement to P-014
cancellation email), secondarily as a general "quick SMS" feature. Technically analogous
to the email implementation: pre-filled, editable form → POST → send via seven.io REST API.

---

## GDPR Analysis

### Data Protection Assessment

| Aspect | Assessment |
|---|---|
| **Legal basis** | To be clarified — see below |
| **Data transfer** | Phone number + SMS content transmitted to seven.io |
| **Data processing agreement** | seven.io acts as a data processor (Art. 28 GDPR) |
| **Third-country transfer** | ❌ Not an issue — seven.io GmbH, Hamburg, Germany → within EU |
| **Sensitivity** | MEDIUM — content reveals therapy context if SMS is intercepted |

### Legal Basis — Open Question ⚠️

The current treatment contract contains **no clause about SMS communication**.

**Option A — Art. 6(1)(b): "Performance of contract"**
Defensible for *pure appointment cancellations* (appointment is regulated in §4 of the
treatment contract; the phone number is collected for appointment communication).
However: only applies to narrowly-scoped appointment cancellations, not to a general
"quick SMS" feature.

**Option B — Consent in the treatment contract (recommended)**
Cleanest solution, covers general messages too. Add a line to `behandlungsvertrag_pdf.html` (DE + EN):
> *"Ich willige ein, dass mir der Therapeut terminbezogene Mitteilungen auch per SMS an die angegebene Telefonnummer senden darf."*
> *(I consent to the therapist sending me appointment-related notifications by SMS to the phone number provided.)*

→ **Decide before implementation and update the contract if necessary.**

### Required Measures Before Go-Live

1. **Clarify legal basis**: Choose option A or B (see above); if option B, update treatment contract

2. **Sign DPA**: seven.io provides a data processing agreement (DPA).
   - URL: https://www.seven.io/de/company/avv/
   - Online signing available — takes ~5 minutes

3. **Update DPIA** (`docs/operations/DPIA.md`):
   - New category in table "Categories of personal data": phone number
   - New row "External service providers": seven.io GmbH (Frankfurt/Hamburg)
   - Risk assessment: SMS content implicitly contains therapy context → risk LOW
     (therapy context is not explicit; therapist's name not strictly required)

4. **Update privacy notice for clients** (if one exists):
   - Mention "appointment notifications by SMS via seven.io"

5. **Practice rule**: SMS content must not contain explicit therapy diagnoses/content —
   only appointment references ("Our session tomorrow"). Enforced via form pre-fill text.

### Acceptable Residual Risk
- SMS as a channel is generally less secure than email (metadata at network operator)
- For pure appointment administration (no clinical content) the risk is acceptable
- Clients already use email for the same purpose

---

## Technical Specification

### Dependencies

```
# Add to requirements.txt:
sms77api>=1.0.0
```

### Configuration (`.env`)

```
SEVEN_API_KEY=<API key from seven.io dashboard>
```

### Model: no new model needed

Phone number comes from `client.phone` (existing field).
Optional logging: SMS sending via existing `logger.info()` pattern.

### View: `SendSmsView`

Analogous to `SendCancellationEmailView` in `email_views.py`:
- `GET`: pre-filled form (recipient number + editable text)
- `POST`: send via `sms77api.Sms77api`, redirect to `client_detail`

**Form**: `SmsForm` (new, simple) — fields: `recipient` (phone number), `message` (textarea)

**Pre-filled text (DE)**:
```
[Anrede], unsere morgige Sitzung muss ich leider aus Krankheitsgründen absagen. Melde mich!
```

**Pre-filled text (EN)**:
```
[Salutation], I'm afraid I have to cancel tomorrow's session due to illness. Will be in touch!
```

SMS must be short (160 characters); salutation = `client.salutation` or first name.

### URL Pattern

```
clients/<int:pk>/sms/
name="send_sms"
```

### Template: `send_sms.html`

Analogous to `send_cancellation_email.html` but with character counter (JS, 160-character limit warning).

### Button on `client_detail.html`

Next to the existing "🤒 Sitzung absagen" email button, shown only when `client.phone` is set:

```html
{% if client.phone %}
<a href="{% url 'send_sms' client.pk %}" class="btn btn-secondary"
   title="SMS wegen Absage senden">
    📱 SMS senden
</a>
{% endif %}
```

---

## Implementation Plan

### Phase 1: Backend (2h)
- [ ] `sms77api` to `requirements.txt`
- [ ] `SEVEN_API_KEY` to `.env.example` + settings loader
- [ ] `SmsForm` in `forms.py` or new `sms_forms.py`
- [ ] `SendSmsView` in `email_views.py` (or new `sms_views.py`)
- [ ] URL + `__init__.py` + `__all__` update

### Phase 2: Frontend (1h)
- [ ] `send_sms.html` template
- [ ] SMS button on `client_detail.html`
- [ ] Character counter (JS, warns at >160 characters)

### Phase 3: GDPR & Configuration (1h)
- [ ] Sign DPA with seven.io (online)
- [ ] Update `DPIA.md`
- [ ] Obtain API key + add to `.env`
- [ ] Smoke test with own number

---

## Test Checklist
- [ ] SMS sending to test number works
- [ ] Error message when API key is missing (graceful)
- [ ] Error message when `client.phone` is empty
- [ ] DE/EN text correct
- [ ] Character counter warns at >160 characters
- [ ] API key not exposed in logs/templates

---

## Notes

- **Cost**: seven.io ~€0.065 per SMS (Germany) — negligible for a solo practice
- **Account**: API key not yet obtained → smoke test with own number as first step
- **Channel choice**: SMS for short urgent messages; email for formal communication
  (cancellation email remains; SMS is an additional option)
- **General SMS feature**: Could later be extended to free-form messages (not only cancellations)
