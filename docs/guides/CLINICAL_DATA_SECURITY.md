# Clinical Data Security — What This App Does and What You Provide

Clinical documentation (session logs, client profiles, supervision notes) is the most
sensitive data in this system. This guide explains the app's security model, what
infrastructure you are responsible for, and the open compliance questions every adopter
should resolve before storing real client data.

---

## What the App Encrypts

Clinical note fields use **Fernet symmetric encryption** (from the `cryptography` package).
The following fields are encrypted at rest in the database:

| Model | Encrypted fields |
|---|---|
| `ClientProfile` | `intake_notes`, `case_notes` |
| `SessionLog` | `content`, `interventions`, `therapist_reflection` |
| `SupervisionItem` | `content` |
| `ClientNote` | `content` |

Session metadata (`session_date`, `session_type`, `mood_tags`) is intentionally
**not encrypted** — it is needed for scheduling, triage, and filtering without
decrypting the full note.

The encryption key is `FERNET_KEY` in your `.env`. **Losing this key means losing
access to all clinical notes permanently.** Back it up in a separate location from
the database.

---

## What You Must Provide

The app's field-level encryption protects data inside the database. The surrounding
infrastructure is your responsibility:

- **Full-disk encryption** — LUKS (Linux), FileVault (macOS), or BitLocker (Windows)
  ensures data is unreadable if the machine is physically stolen.
- **Encrypted backups** — database dumps and media files must be encrypted before
  being stored on external media or a NAS. See [BACKUP_SETUP.md](BACKUP_SETUP.md).
- **Key storage** — `FERNET_KEY`, `POSTGRES_PASSWORD`, and `DJANGO_SECRET_KEY` must
  be backed up securely and separately from the data they protect (e.g. a password
  manager, not a file on the same disk).

---

## Legal Requirements (Germany / DACH)

### DSGVO Art. 9 — Health Data (Besondere Kategorie)

Clinical notes are special-category data under DSGVO. Before storing them you need:

1. **Explicit client consent** for digital storage with encryption — your intake
   consent form should cover this. Check with your Berufsverband for a template.
2. **Documented purpose limitation** — clinical notes are for therapeutic use only;
   document this in your DPIA.
3. **Data Protection Impact Assessment (DPIA)** — required for Art. 9 processing.
   See [`docs/operations/DPIA-template.md`](../operations/DPIA-template.md) for
   a fillable starting point.

### Retention vs. Erasure

Heilpraktiker in Germany must retain client records for **10 years** after treatment ends.
DSGVO Art. 17 gives clients the right to erasure. These conflict.

A common approach: **pseudonymise** records after the treatment relationship ends —
retain session dates and clinical content, but detach them from the client's identifying
personal data. No automated pseudonymisation is implemented yet.

---

## Open Questions

Resolve these before going live with real client data:

1. **Data portability** (DSGVO Art. 20) — clients can request their data in a portable
   format. No export function is implemented yet.

2. **Right to erasure policy** — document how you handle a deletion request that
   conflicts with the 10-year retention obligation.

3. **FERNET_KEY rotation** — what happens if the key is compromised? There is no
   built-in re-encryption command. Plan a key rotation procedure before you need it.

4. **Audit trail** — there is no log of who accessed which clinical record and when.
   For a single-user system this is low priority; it becomes important if multi-user
   access is added (see [EMERGENCY_ACCESS_PLANNING.md](EMERGENCY_ACCESS_PLANNING.md)).

5. **Full-text search** — encrypted fields cannot be searched with `ILIKE`. If you
   need to search across session notes (e.g. "find all mentions of X"), that requires
   either decrypting at query time (slow) or maintaining a separate unencrypted index
   (privacy tradeoff). Currently not implemented.

---

## Resources

- DSGVO Art. 9: <https://dsgvo-gesetz.de/art-9-dsgvo/>
- DSGVO Art. 17 (right to erasure): <https://dsgvo-gesetz.de/art-17-dsgvo/>
- DSGVO Art. 20 (data portability): <https://dsgvo-gesetz.de/art-20-dsgvo/>
- Fernet encryption: <https://cryptography.io/en/latest/fernet/>
- DPIA template: [../operations/DPIA-template.md](../operations/DPIA-template.md)
- Django security: [../operations/SECURITY.md](../operations/SECURITY.md)
