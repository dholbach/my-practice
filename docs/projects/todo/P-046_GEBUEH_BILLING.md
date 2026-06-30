# P-046: GebüH-Abrechnung

## Scope note

This feature is only relevant for therapists with the title **Heilpraktiker** or
**Heilpraktiker für Psychotherapie**. Clients with private insurance or public-aid
entitlement expect a GebüH-structured invoice so their insurer can reimburse costs.
Self-paying clients without reimbursement claims skip all of this (controlled by the
`client_needs_gebueh_invoice` flag, see Phase 1c).

## Goal

Capture GebüH billing codes (Ziffern) per session and generate GebüH-compliant invoices
for clients whose insurer requires itemised billing. The agreed practitioner fee
(vereinbarter Betrag) remains the total; the GebüH line items plus a Restbetrag decompose
it — the insurer reimburses within the GebüH limits, the rest is billed directly.

## Key design decisions

- `Leistungserfassung` links to `Session` (not `InvoiceItem`). Session is the clinical
  event; billing flows from it. An InvoiceItem is generated later and may span multiple
  sessions.
- **No Faktor field.** GebüH billing always uses `satz_max` (the highest rate in the
  range). The Faktor 1.0–2.3 concept is GOÄ logic and does not apply here. The insurer
  reimburses the Höchstsatz without negotiation.
- `betrag` on `Leistungserfassung` = `ziffer.satz_max`, stored at entry time so it
  survives future rate table updates.
- `vereinbarter_betrag` per session is derived from `client.hourly_rate_60` ×
  `(session.duration / 60)` at entry time and stored so it survives rate changes.
- Frequency validation is a soft warning — never a hard block. The therapist decides.
- GebüH output is conditional: only rendered when `client_needs_gebueh_invoice = True`.

---

## Phase 1 — Data models

### 1a. `GebuhZiffer` model (`models/gebueh.py`)

```python
class GebuhZiffer(models.Model):
    nummer       = models.CharField(max_length=10)     # "19.2"
    bezeichnung  = models.CharField(max_length=300)
    satz_max     = models.DecimalField(max_digits=8, decimal_places=2)  # Höchstsatz, used for billing
    satz_min     = models.DecimalField(max_digits=8, decimal_places=2)  # reference only, not billed
    anmerkung    = models.TextField(blank=True)        # "nur als Alleinleistung"
    max_haeufigkeit    = models.PositiveSmallIntegerField(null=True, blank=True)
    bezugszeitraum_tage = models.PositiveSmallIntegerField(null=True, blank=True)
```

Register in `models/__init__.py` and admin.

### 1b. Seed data — fixture or data migration

Relevant Ziffern (GebüH rates as provided; verify against current index before shipping):

**Anamnese / Erstgespräch**

| Ziffer | Bezeichnung | Satz min | Satz max | Anmerkung | max_haeufigkeit | bezugszeitraum_tage |
|--------|-------------|----------|----------|-----------|-----------------|---------------------|
| 1 | Anamnese / Folgeanamnese | 15,40 € | 41,00 € | Erstanamnese 1× jährlich; Folgeanamnese 3× in 6 Monaten | — | — |
| 19.5 | Psychologische Exploration mit eingehender Beratung | 15,50 € | 46,00 € | | | |

**Laufende Behandlung**

| Ziffer | Bezeichnung | Satz min | Satz max | Anmerkung | max_haeufigkeit | bezugszeitraum_tage |
|--------|-------------|----------|----------|-----------|-----------------|---------------------|
| 19.1 | Psychotherapie bis 30 Min | 15,50 € | 26,00 € | | | |
| 19.2 | Psychotherapie 50–90 Min | 26,00 € | 46,00 € | Übliche Ziffer für reguläre Sitzung | | |
| 19.8 | Behandlung durch Hypnose (Einzelperson) | 15,50 € | 26,00 € | | | |

**Diagnostik / Sonstiges**

| Ziffer | Bezeichnung | Satz min | Satz max | Anmerkung | max_haeufigkeit | bezugszeitraum_tage |
|--------|-------------|----------|----------|-----------|-----------------|---------------------|
| 19.3 | Ausstellung eines psychodiagnostischen Befundes | 15,50 € | 38,50 € | | | |
| 19.6 | Anwendung / Auswertung von Testverfahren (z.B. TAT, Rorschach) | 15,50 € | 38,50 € | | | |
| 19.4 | Psychotherapeutisches Gutachten (je Seite) | — | 15,50 € | Abrechnung je angefangene Seite | | |
| 4 | Eingehende Beratung ≥ 15 Min | 16,40 € | 22,00 € | Nur als Alleinleistung pro Sitzung erstattungsfähig | | |

**Model note — Ziffer 1 has two distinct frequency rules:**
- Erstanamnese: 1× per calendar year
- Folgeanamnese: 3× within 180 days

The single `max_haeufigkeit` / `bezugszeitraum_tage` pair on `GebuhZiffer` cannot
express both rules simultaneously. Options:
  a) Store the Folgeanamnese rule (3× / 180 days) as the model-level constraint and
     add a free-text `anmerkung` for the yearly Erstanamnese limit — the therapist
     reads it; no automated check for the rarer case.
  b) Split Ziffer 1 into two separate rows (`1a Erstanamnese`, `1b Folgeanamnese`).
     Cleaner logic, but diverges from the official single-Ziffer number.

Option (a) is recommended for the initial implementation. Revisit if automated
Erstanamnese tracking is needed later.

Deliver as a data migration (`0XXX_seed_gebueh_ziffern.py`) using `get_or_create`
so re-running is safe.

### 1c. `Client` model additions

```python
needs_gebueh_invoice = models.BooleanField(default=False, ...)
diagnose_gebueh = models.CharField(max_length=300, blank=True,
    help_text="Diagnose für GebüH-Rechnung. Leer = 'Probatorik'.")
```

### 1d. `Leistungserfassung` model

```python
class Leistungserfassung(TimestampedModel):
    session  = models.ForeignKey(Session, on_delete=models.PROTECT, related_name="gebueh_leistungen")
    ziffer   = models.ForeignKey(GebuhZiffer, on_delete=models.PROTECT)
    betrag   = models.DecimalField(max_digits=8, decimal_places=2)  # = ziffer.satz_max at entry time
    vereinbarter_betrag = models.DecimalField(max_digits=8, decimal_places=2)
    # derived at save from client.hourly_rate_60 × (session.duration / 60)
```

Both fields are stored (not computed) so they survive future changes to the rate table or
client's hourly rate. No Faktor field — the Höchstsatz is always used.

---

## Phase 2 — Quick-entry UI

### Entry point

After a session is completed (or from the session detail page): a **"GebüH erfassen"**
link/button that opens a compact form. Only shown when
`session.client.needs_gebueh_invoice = True`.

### Form design (target: <30 seconds)

- Checkbox list of the 8 most common Ziffern with their names + `satz_max` shown
- No Faktor input — the Höchstsatz is billed automatically on selection
- Submit → creates `Leistungserfassung` rows with `betrag = ziffer.satz_max`

### Validation / warnings (soft — no hard block)

**Frequency check** (Ziffer 19.5 and similar):
```
Achtung: 3. Folgeanamnese in 180 Tagen — regulär nur 3× abrechenbar.
```
Query: count `Leistungserfassung` for this client + this ziffer within
`ziffer.bezugszeitraum_tage` days before today.

**Alleinleistung check** (Ziffer 1, Ziffer 4):
If the user selects Ziffer 4 (or Ziffer 1) alongside any other ziffer,
show:
```
Achtung: Ziffer 4 ist nur als Alleinleistung erstattungsfähig.
```
Implement as a Django form `clean()` that adds a `non_field_errors` warning
(not a validation error — the user can still save).

---

## Phase 3 — Invoice integration

### 3a. Invoice generation

When building an invoice for a client with `needs_gebueh_invoice = True`,
gather all `Leistungserfassung` entries for sessions in the invoice period.

Group by session. Per session block:

| Ziffer | Bezeichnung | Datum | Betrag |
|--------|-------------|-------|--------|
| 19.2 | Psychotherapie 50–90 Min | 12.06.2026 | 46,00 € |
| 19.5 | Psychologische Exploration | 12.06.2026 | 46,00 € |
| | **Zwischensumme GebüH** | | 92,00 € |
| | Restbetrag | | 58,00 € |
| | **Sitzung gesamt** | | **150,00 €** |

**Restbetrag** = `vereinbarter_betrag` − Zwischensumme GebüH.
Clamped to 0 if GebüH sum > vereinbarter_betrag (warn in UI, not on PDF).

**Gesamtsumme** = sum of all `vereinbarter_betrag` values (= sum of GebüH + Restbeträge).

### 3b. Diagnose line

On invoices where `client.needs_gebueh_invoice = True`, render:

```
Diagnose: {{ client.diagnose_gebueh|default:"Probatorik" }}
```

Placed above the session table.

### 3c. PDF template update

Both `invoice_pdf_de.html` and `invoice_pdf_en.html` need a conditional GebüH block.
The existing per-session line-item layout is replaced (for GebüH clients) with the
itemised table above. Non-GebüH clients: unchanged.

---

## Phase 4 — Client profile UI hint

In the client detail view / Profil tab, when
`client.needs_gebueh_invoice = True` **and** `client.diagnose_gebueh` is blank:

Show a subtle callout:
```
Diagnose noch nicht gesetzt — aktuell wird "Probatorik" auf der Rechnung verwendet.
Nach Abschluss der probatorischen Phase bitte Diagnose aktualisieren.  [Bearbeiten →]
```

Trigger to prompt update: once Ziffern 1, 19.5, or 19.6 have been recorded 5+ times
(end of probatory phase heuristic), escalate callout to a warning badge.

---

## Relevant files

- `app/my_practice/models/gebueh.py` — new (GebuhZiffer, Leistungserfassung)
- `app/my_practice/models/client.py` — add `needs_gebueh_invoice`, `diagnose_gebueh`
- `app/my_practice/models/__init__.py` — export new models
- `app/my_practice/views/session_views.py` — add GebüH entry view
- `app/my_practice/utils/invoice_helpers.py` — extend with GebüH item aggregation
- `app/templates/my_practice/invoice_pdf_de.html` — conditional GebüH block
- `app/templates/my_practice/invoice_pdf_en.html` — same
- `app/my_practice/migrations/` — model migration + seed data migration
- `app/my_practice/tests/test_gebueh.py` — new

---

## Work estimate

| Phase | Work |
|-------|------|
| 1a–1d Models + migration + seed | 2 days |
| 2 Quick-entry UI + validation | 2 days |
| 3 Invoice integration + PDF | 2 days |
| 4 Client profile hint | 0.5 day |
| Tests | 1 day |
| **Total** | **~7–8 days** |

Two natural milestones for splitting into PRs:
1. **PR 1** — models + seed + admin (phases 1a–1d); no UI yet, but data is in place
2. **PR 2** — quick-entry UI + validation (phase 2)
3. **PR 3** — invoice integration + PDF (phase 3)
4. **PR 4** — client hint + polish (phase 4)

## Open questions before starting

- **GebüH rates**: the rates in the seed table above were confirmed by the practitioner.
  Cross-check once more against the current official GebüH index before writing the seed
  migration, as the 1985 schedule has been informally updated. (`satz_min` is stored for
  reference but never billed.)
- **vereinbarter_betrag source**: currently derived from `client.hourly_rate_60 ×
  (session.duration / 60)`. Is this always correct, or can individual sessions have
  a different rate (e.g. sliding-scale adjustments)?
- **Existing InvoiceItem structure**: GebüH invoices will look quite different from
  the current duration-based InvoiceItem format. Should they use the same `InvoiceItem`
  model (adding a `leistungserfassung` FK) or sit alongside it as a separate line-item
  source? The cleaner path is a separate source, but it means the invoice total must
  be reconciled from two sources.
- **Restbetrag can be negative**: if GebüH Höchstsätze exceed the vereinbarter Betrag
  (GebüH rates from 1985 sometimes exceed modern discounted fees for short sessions),
  the Restbetrag goes negative. The spec says clamp to 0 and warn — confirm this is
  the right UX rather than surfacing the overshoot to the client.
