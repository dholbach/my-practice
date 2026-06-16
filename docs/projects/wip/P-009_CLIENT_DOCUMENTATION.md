# P-009: Client Documentation System

**Status**: ✅ Core implemented — ongoing refinements  
**Security Level**: 🔴 CRITICAL — Gesundheitsdaten (Art. 9 DSGVO)

---

## What's Implemented

### Models (`models/clinical.py`)

| Model | Fields | Encrypted |
|---|---|---|
| `ClientProfile` | `client` (OneToOne), `intake_notes`, `case_notes`, `arbeitsdiagnose` | content fields (Fernet) |
| `SessionLog` | `session` (OneToOne), `session_type`, `mood_tags` (JSON), `content`, `interventions`, `therapist_reflection` | content fields (Fernet) |
| `SupervisionItem` | `client`, `content`, `status` | `content` (Fernet) |
| `ClientNote` | `client`, `note_date`, `content` | `content` (Fernet) |

All models inherit `TimestampedModel`. Session metadata (`session_type`, `mood_tags`)
is intentionally **unencrypted** for triage use.

### Views (`views/clinical_views.py`)

- `client_profile_save` — create/update ClientProfile
- `session_log_create` / `session_log_edit` — create/edit SessionLog; edit can update session duration
- `supervision_item_create` / `supervision_item_toggle` — add + toggle supervision items (AJAX-capable)
- `supervision_queue` — cross-client supervision dashboard
- `client_triage_summary` — emergency printable triage (unencrypted metadata only)
- `client_note_create` / `client_note_delete` — dated free-text notes per client

### UI (`templates/my_practice/client_detail.html`)

Client detail page has a 4-tab clinical workspace:

1. **Profil** — `arbeitsdiagnose`, `intake_notes`, `case_notes` with markdown preview
2. **Sitzungen** — session list: date / interventions | markdown content
3. **Supervision** — items with status toggle
4. **Notizen** — dated free-text notes

### Infrastructure

- `markdown==3.8` + `render_markdown` templatetag (`nl2br`, `sane_lists`, `fenced_code`)
- Fernet encryption via `FERNET_KEY` env var
- Admin classes for `ClientProfile`, `SessionLog`, `SupervisionItem`
- Test coverage: `tests/test_clinical.py` — models, encryption round-trips, views, mood tags, triage

### Onboarding widget (sidebar)

Three-step process tracker: **Aufnahme → Vertrag → Anamnese → Abschließen**, each with mark-done / undo.

---

## Remaining / Open Items

### Legal & Compliance

- [ ] **Data portability export** (DSGVO Art. 20) — export a client's full record as a
  portable file; ~4h code; nobody is asking for this urgently
- [ ] **Erasure / pseudonymisation policy** — document the conflict between DSGVO Art. 17
  (right to erasure) and the 10-year Aufbewahrungspflicht; no code needed
- [ ] **ClientNote admin registration** — 5-minute item

### Features (Low Priority / If Needed)

- [ ] **`ClientDocument` model** — PDF upload for intake forms, contracts; ~1–2 days;
  access-control design depends on P-010 multi-user work

---

## Related

- Security and encryption details: [`docs/guides/CLINICAL_DATA_SECURITY.md`](../../guides/CLINICAL_DATA_SECURITY.md)
- Emergency access / crisis fields: [`docs/guides/EMERGENCY_ACCESS_PLANNING.md`](../../guides/EMERGENCY_ACCESS_PLANNING.md)
- DPIA template: [`docs/operations/DPIA-template.md`](../../operations/DPIA-template.md)
