# Data Protection Impact Assessment (DPIA) — Template

**Pursuant to GDPR Art. 35**

> **How to use this template**
>
> A DPIA is required under GDPR Art. 35 whenever you process **special category data**
> (Art. 9) at scale or in a way likely to result in high risk to individuals. Therapy
> practice records — health data, clinical notes — qualify.
>
> Fill in all `[PLACEHOLDER]` sections for your practice. Items marked with a footnote
> explain what to consider. Have the completed document reviewed by a data protection
> advisor or your professional association before going live with clinical data.
>
> Keep the completed version **outside this repository** (it contains personal data).
> A gitignored copy at `docs/operations/DPIA.md` is the intended location.

---

## 1. Description of Processing

### Purpose
Administration of a single-therapist practice: invoicing, client management,
income and expense tracking for tax purposes.

### Categories of Personal Data

| Data Category | Fields | Legal Basis |
|---|---|---|
| Client master data | Name, address, email, phone, date of birth | Art. 6(1)(b) GDPR |
| Session data | Date, duration, service type, fee | Art. 9(2)(h) GDPR |
| Financial data | Invoice numbers, amounts, payment date | Art. 6(1)(c) GDPR (§ 147 AO) |
| Client code | Anonymised reference code (e.g. AB-1) | — |
| Clinical notes | `ClientProfile.intake_notes`, `case_notes`, diagnosis field | Art. 9(2)(h) GDPR |
| Session reflections | `SessionLog.content`, `therapist_reflection` | Art. 9(2)(h) GDPR |
| Session metadata | `SessionLog.session_type` (unencrypted) | Art. 9(2)(h) GDPR |
| Supervision content | `SupervisionItem.content` | Art. 9(2)(h) GDPR |

> **Note on clinical fields**: `SessionLog.content`, `therapist_reflection`,
> `ClientProfile.intake_notes`, `case_notes`, and `SupervisionItem.content` are
> stored encrypted (Fernet / AES-128-CBC) in the database. Only the `FERNET_KEY`
> holder can read plaintext. Adjust this table if you disable field encryption.

### Explicitly NOT Processed
- Biometric or genetic data
- Psychological test data (questionnaires, scores)
- [Add any other categories you have explicitly decided not to process]

### System Description
- **Deployment**: [Local Docker / VPS / other — describe your setup]
- **Database**: PostgreSQL 17, located on [describe storage and encryption: e.g. LUKS-encrypted filesystem / encrypted VPS volume]
- **Access**: [Single-user, localhost only / describe any remote access]
- **Backups**: [Describe backup method, encryption, and storage locations]
- **External data flows**: Documented in [DATA_REGISTER.md](DATA_REGISTER.md)

---

## 2. Necessity and Proportionality

### Legal Basis
- **Art. 6(1)(b) GDPR**: Performance of contract — invoicing clients
- **Art. 9(2)(h) GDPR**: Healthcare — therapeutic services
- **§ 147 AO (Germany)**: 10-year retention obligation for business records
- [Add any additional applicable legal bases for your jurisdiction]

### Data Minimisation
- Only necessary fields are collected
- Client codes anonymise data in templates and exports
- No disclosure to third parties unless legally required
- [Document any third-party data processors you use, e.g. email provider, SMS gateway]

### Storage Periods
| Data Type | Retention Period |
|---|---|
| Invoices + financial data | 10 years (§ 147 AO) |
| Client master data | Duration of therapy + 10 years |
| Backups | [Your rolling window, e.g. 30 days] |
| Logs | [e.g. Not persisted / 7 days] |
| [Any other data types] | [Retention period + legal basis] |

---

## 3. Risks to Rights and Freedoms

### Risk 1: Data Breach (Theft, Loss of Device)
| Aspect | Assessment |
|---|---|
| **Likelihood** | MEDIUM (device theft possible) |
| **Severity** | HIGH (sensitive health data) |
| **Mitigation** | [Your encryption measures — e.g. full-disk encryption + backup encryption] |
| **Residual risk after mitigation** | [LOW / MEDIUM — your assessment] |

### Risk 2: Unauthorised Access (Hacking, Social Engineering)
| Aspect | Assessment |
|---|---|
| **Likelihood** | [LOW / MEDIUM — depends on your deployment] |
| **Severity** | HIGH |
| **Mitigation** | [Your access controls — e.g. strong passphrases, 2FA, no remote access] |
| **Residual risk after mitigation** | [Your assessment] |

### Risk 3: Data Loss (Hardware Failure, Accidental Deletion)
| Aspect | Assessment |
|---|---|
| **Likelihood** | LOW (with backups) |
| **Severity** | MEDIUM (operational continuity) |
| **Mitigation** | [Your backup strategy — media, frequency, off-site] |
| **Residual risk after mitigation** | LOW |

> Add further risks if relevant to your setup (e.g. cloud hosting, shared infrastructure,
> employee access, third-party integrations).

---

## 4. Technical and Organisational Measures (TOMs)

### Technical Measures

| Measure | Status | Details |
|---|---|---|
| Full-disk / volume encryption | [✅ / ❌] | [Technology and scope, e.g. LUKS on nvme0n1p3] |
| Hardware authentication (LUKS / login) | [✅ / ❌] | [e.g. Yubikey FIDO2 via systemd-cryptenroll] |
| Backup encryption | [✅ / ❌] | [Tool and algorithm, e.g. Pika AES-256 + HMAC-SHA256] |
| Backup retention and pruning | [✅ / ❌] | [Retention period and mechanism] |
| No cloud hosting | [✅ / ❌] | [Localhost / self-hosted VPS — describe] |
| No internet-facing application port | [✅ / ❌] | [Docker without external port forwarding / reverse proxy details] |
| Database access internal only | [✅ / ❌] | PostgreSQL via Docker network, no external port |
| Clinical field encryption (Fernet) | [✅ / ❌] | [Fields encrypted, key storage, e.g. FERNET_KEY in .env on encrypted disk] |

### Organisational Measures

| Measure | Status | Details |
|---|---|---|
| Client consent / intake forms | [✅ / ❌] | [Source — e.g. professional association templates] |
| Professional liability insurance | [✅ / ❌] | [Provider / coverage type] |
| Deletion / retention policy | ✅ | Documented in section 2 above |
| Emergency access plan | [✅ / ❌] | [Describe — who can access what in an emergency, and how] |
| Data processing agreements | [✅ / N/A] | [Any third-party processors requiring an Art. 28 DPA] |

---

## 5. Consultation

| Party | Status | Details |
|---|---|---|
| Professional association | [✅ / ❌] | [Intake and consent forms from association] |
| Data protection officer | [Not required / N/A] | Not mandatory for single-person practices without high-volume processing |
| Clients | [✅ / ❌] | [How clients are informed — intake forms, practice information sheet] |
| [Other parties] | | |

---

## 6. Outcome and Approval

The data protection impact assessment shows that the identified risks have been reduced to
an acceptable residual risk through the implemented technical and organisational measures.

**Practitioner**: [YOUR FULL NAME]  
**Practice**: [PRACTICE NAME / ADDRESS]  
**Date completed**: [DATE]  
**Last reviewed**: [DATE]

**Assessment**:

| Aspect | Assessment |
|---|---|
| **Risk to data subjects** | [HIGH before measures / LOW after] |
| **Measures implemented** | [Summary: disk encryption + field encryption + localhost-only] |
| **SQL access to clinical notes** | [Only Fernet ciphertext visible if field encryption active] |
| **Backup compromise** | [Clinical fields remain protected by Fernet even if backup is decrypted] |
| **Overall residual risk** | [LOW / MEDIUM — your final assessment] |

**Filing**: Retain with practice records. Export as PDF and file in the physical records
folder (recommended).

---

*Template for my-practice — based on GDPR Art. 35 | Adapt for your jurisdiction and setup*
