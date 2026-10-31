# Clinical Data Security — What This App Does and What You Provide

Clinical documentation (session logs, client profiles, supervision notes) is the most
sensitive data in this system. This guide explains the app's security model, what
infrastructure you are responsible for, and the open compliance questions every adopter
should resolve before storing real client data.

---

## What the App Encrypts

Free-text fields that hold health information, plus the credentials that open the
practice calendar, use **Fernet symmetric encryption** (from the `cryptography` package).
The following fields are encrypted at rest in the database:

| Model | Encrypted fields |
|---|---|
| `ClientProfile` | `intake_notes`, `case_notes`, `arbeitsdiagnose` |
| `SessionLog` | `content`, `interventions`, `therapist_reflection`, `next_session_ideas` |
| `SupervisionItem` | `content`, `resolution_notes` |
| `ClientNote` | `content` |
| `Client` | `notes` |
| `ClientInquiry` | `notes`, `initial_contact_notes` |
| `GoogleCalendarToken` | `token`, `refresh_token`, `client_secret` |

`my_practice/tests/test_encryption.py` fails if any of these stops being encrypted.
Encrypted fields cannot be searched, so the client list search covers name, code and
email but not notes.

Uploaded **client documents** (intake forms, questionnaires, contracts, doctors'
letters) are encrypted too: each file under `media/clients/` is stored as a single
Fernet token under the same `FERNET_KEY` (`my_practice/storage.py`), and is decrypted
only when an authorised user opens it. Documents uploaded before this existed are
encrypted in place by migration `0006` on the next start. Expense receipts and the
practice logo/signature are not health data and stay plain files.

Database dumps and the media archive in a backup therefore hold ciphertext for all of
the above — and **restoring them needs the `FERNET_KEY`** they were written with.

Session metadata (`session_date`, `session_type`, `mood_tags`) is intentionally
**not encrypted** — it is needed for scheduling, triage, and filtering without
decrypting the full note.

The encryption key is `FERNET_KEY` in your `.env`. **Losing this key means losing
access to all encrypted content permanently.** Back it up in a separate location from
the database. `./dev.py manage encryption check` (or `docker compose exec django
python manage.py encryption check` in production) confirms the configured key opens
every stored value — run it after restoring a backup onto a new machine.

### Rotating the key

If the key may have leaked, or as routine hygiene:

1. Generate a new key and put it **in front of** the old one:
   `FERNET_KEY=<new>,<old>` — the first key encrypts, every listed key decrypts.
2. Restart, then run `manage.py encryption rotate` — re-encrypts every value under
   the new key (one transaction; it refuses and changes nothing if any value is
   unreadable). The app can stay up: a value saved while it runs is kept, not
   overwritten with the older content, and a document deleted meanwhile is skipped.
3. Run `manage.py encryption check` with only the new key set, then drop the old one.
4. Old database backups still need the old key — keep it with them until they expire.

A value that no configured key can open stops the page with an `EncryptionKeyError`
naming the field — the app never shows or re-saves undecryptable data.

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

3. **Audit trail** — there is no log of who accessed which clinical record and when.
   For a single-user system this is low priority; it becomes important if multi-user
   access is added (see [EMERGENCY_ACCESS_PLANNING.md](EMERGENCY_ACCESS_PLANNING.md)).

4. **Full-text search** — encrypted fields cannot be searched with `ILIKE`. If you
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
