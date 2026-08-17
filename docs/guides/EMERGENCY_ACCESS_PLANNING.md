# Emergency Access Planning — A Guide for Solo Practitioners

If you run this system alone, you need a plan for what happens when you are temporarily
or permanently unavailable (illness, accident, death). Your clients need continuity of
care; your practice needs an administrative handover. This guide covers what the app
provides, what you must set up yourself, and the open questions worth resolving before
you go live with clinical data.

---

## Legal Context (Germany / DACH)

| Obligation | Source |
|---|---|
| Data protection responsibility (who steps in?) | DSGVO Art. 32 |
| 10-year record retention after your death | Heilpraktiker-Gesetz |
| Client continuity / referral | Professional ethics, Berufsverband guidelines |
| Clinical safety for at-risk clients | Standard of care |

---

## Recommended Architecture: Two Roles

Separate clinical continuity from administrative handover — they require different
expertise and different access levels:

| Role | Suggested Person | What They Need |
|---|---|---|
| **Crisis buddy** | Therapist colleague | Client contact list, crisis contacts, no session notes |
| **Admin buddy** | Accountant or trusted colleague | Invoice list, cost carrier contacts, no clinical data |

These can be the same person, but splitting the roles reduces the access footprint of each.

---

## What This App Provides

**Not yet implemented.** An earlier pass added `crisis_risk`, `emergency_contact_1/2`,
`referring_psychiatrist`, and `backup_therapist` fields on `Client`, plus an admin
"Notfallkontakte" fieldset. That implementation was rolled back before release — it was
too partial to be useful and was blocking other work at the time — so the current
`Client` model has none of this. See [P-010](../projects/todo/P-010_EMERGENCY_ACCESS_PLAN.md)
for the redo. Until then, this guide's "what you must set up yourself" section below
still applies in full — the credentials-vault approach doesn't depend on the app fields.

---

## What You Must Set Up Yourself

None of this depends on the app fields above (which don't exist yet) — it's all
external process, and worth doing regardless of when P-010 lands:

1. **Recruit buddies** — find colleagues or a trusted accountant willing to commit to
   quarterly updates and an annual test of vault access.

2. **Written agreement** — a brief Vertretungsvereinbarung covering: what each buddy
   is authorised to do, confidentiality obligations, and an annual renewal date.
   Check whether your Berufsverband has a standard template.

3. **Credentials vault** — a password manager (e.g. Proton Pass shared vault) with
   the minimum credentials each buddy needs. Keep the crisis vault and admin vault
   separate. Update quarterly.

4. **Client disclosure** — clients should know about the arrangement before it's needed.
   Add a paragraph to your intake/Terms of Care document (see DSGVO Art. 13).

5. **Track crisis contacts outside the app for now** — until P-010 lands, keep
   `emergency_contact_*` / `referring_psychiatrist` / `backup_therapist` info for
   at-risk clients in the credentials vault rather than in the app.

---

## Open Questions to Resolve

Before relying on this plan, clarify with your Berufsverband:

- Can a buddy bill outstanding invoices on your behalf?
- Can they contact cost carriers (KV, BKK) for ongoing sessions?
- Who bears DSGVO Art. 32 responsibility during the transition?
- Who is responsible for the 10-year retention obligation after your death?
- Is a Vertretungsvereinbarung sufficient, or does your professional liability
  insurance require something more formal?

---

## Future App Enhancement: Native Multi-User Access

The current app is single-user. A natural extension would be role-based access:

- **Owner** — full access
- **Crisis buddy** — read-only: client contact list + crisis fields only
- **Admin buddy** — read-only: invoices and financial data only

This is not implemented. Password managers (Proton Pass, Bitwarden) fill the gap in
the meantime, with the tradeoff that credential sharing is coarser than per-record
Django permissions.

---

## Related

- App emergency fields: not yet implemented — see [P-010](../projects/todo/P-010_EMERGENCY_ACCESS_PLAN.md)
- Clinical data security: [CLINICAL_DATA_SECURITY.md](CLINICAL_DATA_SECURITY.md)
- DPIA template: [../operations/DPIA-template.md](../operations/DPIA-template.md)
