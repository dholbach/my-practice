# P-010: Emergency Access Plan

**Status**: 🔲 To Do — earlier implementation rolled back

---

## Background

An earlier pass added `crisis_risk`, `emergency_contact_1/2`, `referring_psychiatrist`,
and `backup_therapist` fields directly on `Client`, plus a collapsible admin
"Notfallkontakte" fieldset and a client-detail crisis section. That implementation was
rolled back before release — it was too partial to be useful in practice and was
blocking other work at the time. No trace of it survives in the current model,
migrations, or admin.

## What's Needed

Redo the data model — fields on `Client` as before, or a small related model if that
fits the UI better — plus the admin fieldset and client-detail display, per the
framework in [`docs/guides/EMERGENCY_ACCESS_PLANNING.md`](../../guides/EMERGENCY_ACCESS_PLANNING.md).

## Remaining (Organisational, unaffected by the code status)

Buddy recruitment, Proton Pass vault setup, colleague agreements, and client
disclosure steps are personal operational work — see `memory/PERSONAL_TODO.md`.

## Guide

The framework (two-role model, legal context, open questions for your Berufsverband)
is documented for OSS adopters in
[`docs/guides/EMERGENCY_ACCESS_PLANNING.md`](../../guides/EMERGENCY_ACCESS_PLANNING.md).
