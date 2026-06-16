# Data Register — External Data Flows

**Scope**: Data that leaves the local system or reaches a third-party processor.  
Internal-only processing (database, backups, PDF rendering) is covered in [DPIA-template.md](DPIA-template.md).  
**Last updated**: May 2026

---

## Overview

| Use-case | Data shared externally | Processor | Opt-in required? | Status |
|----------|----------------------|-----------|-----------------|--------|
| Calendar import (Google Calendar) | None — app reads only | Google | No (existing Google account) | ✅ Active |
| Payment reminder email | Client email address, invoice amount, due date | Email provider (user's account) | No (contractual) | ✅ Active |
| Cancellation email | Client email address, free-text message | Email provider (user's account) | No (contractual) | ✅ Active |
| Bank statement import | None — CSV parsed locally | None | — | ✅ Active |
| SMS appointment reminder / broadcast | Client mobile number, generic message text | seven.io | **Yes — explicit opt-in** | ⏳ Planned (P-023) |

---

## Use-case detail

### Google Calendar import

**What the app does**: Reads calendar events (title, date, start time, duration) to
create Session records and auto-match to clients.

**What travels externally**: Nothing. The app is a read-only OAuth consumer. Client
data is never written back to Google Calendar.

**What Google can infer**: Google holds the full calendar, which may contain client
references in event titles if the practitioner named events that way (e.g.
using a client code like "AG" or "KC" rather than a full name).

**Client-facing description**: The practitioner uses Google Calendar to manage
appointments. Calendar data is read by the practice management system to pre-fill
session records; nothing is written back.

**Legal basis**: Art. 6(1)(b) GDPR — administration of the therapeutic contract.  
**DPA with Google**: Google Workspace Terms of Service + Data Processing Amendment.

---

### Payment reminder / cancellation email

**What the app does**: Generates a draft email (recipient address, subject, body) and
opens it in the user's mail client. The user reviews and sends manually.

**What travels externally**: To/from address, subject line, body text (invoice number,
amount, appointment reference).

**What the email provider can infer**: That the recipient has an outstanding invoice
with the sender. No clinical information in the message body.

**Client-facing description**: Invoice reminders and appointment cancellation notices
are sent by email from the practitioner's personal email account.

**Legal basis**: Art. 6(1)(b) GDPR — performance of contract.  
**DPA with email provider**: Depends on provider (Posteo, Google, etc.); user is
responsible for ensuring their email provider meets GDPR requirements.

---

### Bank statement import

**What the app does**: Parses a locally exported CSV from the user's bank (DKB/ING
format). All matching logic runs locally. No data is sent anywhere.

**What travels externally**: Nothing.

**Legal basis**: Art. 6(1)(c) GDPR — §147 AO tax record-keeping obligation.

---

### SMS — appointment reminder / broadcast message (planned, P-023)

**What the app does**: Sends an SMS via the seven.io API to notify a client of an
appointment time, or to broadcast a short message (e.g. illness cancellation) to
multiple clients simultaneously.

**What travels externally**: The client's mobile phone number + the message text, over
HTTPS to seven.io's API. The message text contains no name and no clinical content —
only time/date or a brief free-text notice.

**What seven.io can infer**: That the phone numbers contacted via the same API key are
associated with the same sender (i.e. belong to clients of the same practice). They do
not receive names, client codes, diagnoses, or any other identifying data beyond the
number itself.

**seven.io background**: seven.io GmbH, Rosenthaler Str. 34–35, 10178 Berlin, Germany.
German company, GDPR-compliant, ISO 27001 certified. EU data residency.

**Client-facing description**:
> "If you opt in, we may send you appointment reminders or short operational notices
> (e.g. illness cancellations) by SMS. Your mobile number is transmitted to seven.io,
> a German SMS provider, solely for delivery of these messages. No name or clinical
> information is included in any SMS. You can withdraw consent at any time."

**Consent mechanism**: Explicit opt-in field on client record (`sms_consent` boolean).
No SMS is sent without `sms_consent = True`. Consent and consent date are logged.

**Legal basis**: Art. 6(1)(a) GDPR — freely given, specific, informed consent.  
**DPA with seven.io**: AVV must be signed before activating the API key (see P-023).

---

## For new use-cases

Before adding any integration that sends client data to a third party:

1. Add a row to the overview table above
2. Write a detail section answering: what data, what can be inferred, client-facing description, legal basis
3. Decide: contractual basis (no new consent needed) or explicit opt-in
4. Check whether a DPA/AVV with the new processor is required
5. Update the client Datenschutzerklärung if a new processor is added
6. Update [DPIA-template.md](DPIA-template.md) if the risk profile changes materially

---

## Existing client notifications

When a new processor is added that wasn't covered by the original intake consent:

- **Contractual basis**: Inform clients by email; no new signature required
- **Consent-based** (like SMS): Opt-in before first use; record consent date in system
- A new full treatment contract is generally **not** required for adding communication
  channels, provided the existing contract covers "appointment communication" broadly
  and clients are clearly informed of the new processor and can decline

---

*Cross-reference: [DPIA-template.md](DPIA-template.md) — system-level risk assessment and TOMs*
