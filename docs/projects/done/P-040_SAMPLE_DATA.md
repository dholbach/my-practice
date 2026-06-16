# P-040 — Sample Data

**Status**: DONE
**Priority**: Medium
**Created**: April 2026
**Completed**: April 2026

---

## Goal

A management command (`seed_sample_data`) that populates a fresh install with realistic,
fictional data — enough to make screenshots compelling and let new users explore the app
without entering anything themselves.

---

## Character Set

40–50 characters drawn from public-domain fiction and mythology, spread across three pools:

| Pool | Source | Examples |
|------|--------|---------|
| Tolkien | LOTR / Silmarillion | Frodo Baggins, Samwise Gamgee, Galadriel, Aragorn, Legolas |
| Le Guin | Earthsea / Hainish | Ged, Tenar, Shevek, Genly Ai, Estraven |
| Greek mythology | Classical | Odysseus, Penelope, Achilles, Medea, Persephone |

Each character gets a client code (e.g. `FB-1`, `GE-2`), a fictional diagnosis theme,
and a realistic session count (3–40 sessions) spread over 12–24 months.

---

## Seasonality

Session distribution should mirror a real therapy practice:

- Summer dip (July–August: ~60% of normal load)
- Christmas/New Year gap (late December: ~0)
- Slightly higher intake in September (post-summer) and January (new-year motivation)
- Random weekly variation ±20%

---

## Session Notes (lorem ipsum theraputica)

Each session gets a short note referencing the character's fictional world in therapy-speak:

> *"Client reports recurring dreams about dark forests and a burden they feel unable to put
> down. Explored themes of responsibility and self-worth. Assigned journaling exercise."*

> *"Client discussed fear of transformation and identity loss. The image of 'becoming
> someone else' recurred. Worked with parts-based framework."*

A pool of ~20 note templates, parametrised by character archetype (hero, exile, ruler,
seeker), shuffled per session.

---

## What Gets Seeded

- Practice (pre-configured with placeholder name, logo slot, bank details)
- 40–50 clients with codes, tags, intake dates
- 200–600 sessions distributed over 2 years
- Invoices (mix of paid / open / overdue) covering ~80% of sessions
- 5–10 open inquiries at various pipeline stages
- A handful of todos and expenses

---

## Implementation Notes

- Management command: `./dev.py manage seed_sample_data [--clear]`
- `--clear` drops all existing data before seeding (for demo resets)
- Use `faker` (already available?) or a static fixture file — static is simpler and reproducible
- All names/codes must pass the existing PII conventions (no real data)
- Idempotent: running twice without `--clear` is a no-op

---

## Out of Scope

- Realistic clinical language beyond the note templates
- Multi-practice seeding
- Media files / documents
