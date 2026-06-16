# P-010: Emergency Access Plan

**Status**: ✅ Code done; organisational setup is personal  
**Completed**: 2026-03

---

## What Was Done

- `Client` model: `crisis_risk`, `emergency_contact_1/2`, `referring_psychiatrist`,
  `backup_therapist` fields added (migration 0047, 2026-03-16)
- Admin: collapsible "Notfallkontakte (P-010)" fieldset + `crisis_risk` list filter
- Client detail view: collapsible crisis section shown when fields are populated

## Remaining (Organisational Only)

The buddy recruitment, Proton Pass vault setup, colleague agreements, and client
disclosure steps are personal operational work — see `memory/PERSONAL_TODO.md`.

## Guide

The framework (two-role model, legal context, open questions for your Berufsverband)
is documented for OSS adopters in
[`docs/guides/EMERGENCY_ACCESS_PLANNING.md`](../../guides/EMERGENCY_ACCESS_PLANNING.md).
