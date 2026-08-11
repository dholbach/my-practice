# P-122: General Freelance Practice Type

**Status**: Concept — Phase 1 has a real near-term trigger, Phase 2 does not
**Priority**: Medium (Phase 1) / Low (Phase 2)
**Created**: August 2026
**Updated**: August 2026 — a concrete third practice is now planned; see below

---

## Timeline (real, not hypothetical)

- **Near-term**: a general-freelance practice (day-rate billing) is being set up,
  staying **Kleinunternehmer** (§ 19 UStG) initially.
- **Later, possibly**: switch to regular VAT registration (Regelbesteuerung) as
  work volume grows — a deliberate conversation with the Finanzamt, not
  automatic. Generally a per-calendar-year election, so it applies going
  forward, not retroactively to invoices already issued.

This splits the work into two phases with very different urgency:

- **Phase 1 — free-form invoice items**: needed **before the first IT invoice
  goes out**. `Practice.is_kleinunternehmer` already exists and already covers
  the tax-treatment side for year one (same field coaching uses today) — no
  schema change needed there. Day-rate billing itself needs no new math either:
  `InvoiceItem.rate × quantity = total` already handles "day rate × number of
  days" generically. The actual blocker is that every `InvoiceItem` still
  requires a `session`, and a multi-day consulting engagement isn't a therapy
  session. **This is now the near-term piece of this doc.**
- **Phase 2 — standard VAT + advance-payment report**: only needed the day the
  Kleinunternehmer election is actually dropped. Clean, concrete trigger to
  build against later — deliberately not built speculatively now.

## Goal

Support a third kind of `Practice` beyond therapy (VAT-exempt, § 4 Nr. 14 UStG) and
coaching (Kleinunternehmer, § 19 UStG): a general freelance business — IT consulting,
workshops, training, book sales, etc. — reusing the existing client/invoicing/tax
infrastructure. Two capabilities are currently missing for that to work:

1. **Standard VAT** — charge VAT on invoices and report it for advance payments
   (Umsatzsteuervoranmeldung).
2. **Free-form invoice items** — line items that aren't tied to a therapy/coaching
   session (e.g. "10 books", "IT consulting, 3h", "workshop day").

---

## What already works, unchanged

- `Practice` is already a fully independent row per business (own address, bank,
  tax config, email templates) — a third practice is just a new row, no schema change.
- `Invoice.tax_rate` / `tax_amount` / `total` already compute real VAT math
  (`subtotal * tax_rate / 100`) — not hardcoded to 0. Both existing practices just
  enter `0.00` today.
- `ServiceType` is practice-scoped and already generic (`code` / `name`) — fits
  "IT consulting hour", "Book", "Workshop day" as-is.
- Everything downstream of `Invoice` (`RevenueCalculator`, `InvoiceFilterHelper`,
  dashboard widgets, `tax_context_builder`, bank reconciliation in `bank_import.py`,
  Focus Queue, PDF/email sending, invoice numbering) operates on `Invoice` header
  fields only (`status`, `total`, `tax_amount`, `paid_date`, `invoice_number`) —
  none of it inspects `InvoiceItem` internals.

## Design decision: item-level flexibility, not a parallel invoice model

Considered and rejected two alternatives during discussion:

- **Separate `FreeFormInvoice` model**: would fork the one invoicing pipeline
  every shared util assumes is singular — `RevenueCalculator`/tax reporting would
  miss the new practice's income unless rewritten to union two tables; bank
  reconciliation matches payments to `Invoice` by number/amount and would need a
  second matching path; `invoice_number` uniqueness is currently one global
  constraint/sequence; CRUD views, forms, templates, PDF, admin would all be
  duplicated.
- **`Invoice` → `SessionInvoice` / `ProjectInvoice` via Django multi-table
  inheritance**: doesn't address where the variation actually lives. Every
  `Invoice` header field (`invoice_number`, `client`, `dates`, `status`, `tax_rate`,
  `notes`) is identical between a session-based and a project-based invoice — only
  the *line item* shape differs. Subclassing the header also reintroduces the
  polymorphic-query problem (`Invoice.objects.filter(...)` returns base rows, not
  typed subclasses, without `django-polymorphic` or manual discriminator logic),
  plus MTI's extra joins/migrations and CRUD/template duplication, all for no
  behavioural gain since the header isn't actually polymorphic.

**Conclusion**: keep one `Invoice` model. Make `InvoiceItem.session` nullable and
add a `description` field used when there's no session. Everything upstream that
already only reads `Invoice` header fields keeps working unmodified; only the
narrow band of code that inspects item internals needs a branch.

---

## Technical Specification (draft)

### Phase 1 (near-term — before first invoice; ~4.5-6.5h)

#### New `Practice` row
- `setup_practice.py` with the IT practice's own name/slug/address/bank/`tax_id`
  (from the new registration)
- `is_kleinunternehmer = True` — reuses the existing field, identical to coaching
  today. No `vat_treatment` field needed yet (see Phase 2).
- `allows_free_form_items = True` — see guardrail flag below; stays `False` for
  therapy/coaching

#### New `Practice.allows_free_form_items` flag (guardrail)
- `BooleanField(default=False)`, same pattern as `is_kleinunternehmer`
- Gates whether a practice's invoice formset offers the free-text row type at
  all, and whether `InvoiceItem.clean()` accepts a description-only item
- Purpose: therapy/coaching keep today's UI and validation completely
  unchanged — a session-less item would silently undercount
  `count_sessions()`-driven analytics and break the clinical-documentation
  link, so it should be structurally impossible there, not just avoided by
  convention

#### `InvoiceItem` changes
- `session` FK: `null=False` → `null=True`
- New `description` field (`CharField` or `TextField`, blank unless `session` is null)
- `save()` / `clean()`: require exactly one of `session` or `description`;
  reject a description-only item unless `self.invoice.practice.allows_free_form_items`
- `__str__`: fall back to `description` when `session_id` is None

#### Ripple points (session-aware code needs a `session_id is None` branch/skip)
- `count_sessions()` (`utils/calculations.py`) — skip items with no session
- Invoice formset UI — per-row branch: session-linked row vs. free-text row,
  free-text row type only offered when `practice.allows_free_form_items`
- PDF line-item rendering (`invoice_pdf_*.html`) — label from `description` when
  no session
- Focus Queue / clinical linkage (`SessionLog`) — already tolerate a `Session`
  existing without a log; a null-session `InvoiceItem` is a smaller version of
  the same "optional link" pattern

#### New `ServiceType` for day-rate billing
- e.g. code `it_day_rate`, name "Consulting (day rate)" — `default_duration`
  is irrelevant here, can be left at its default or ignored for non-session items

### Phase 2 (deferred — triggered by dropping Kleinunternehmer status)

#### `Practice` VAT treatment
- Replace `is_kleinunternehmer: bool` with a `vat_treatment` choice field:
  `exempt_heilpraktiker` / `kleinunternehmer` / `standard_vat`
- `invoice_pdf_de.html` / `_en.html`: currently a hard binary between
  `kleinunternehmer_text` and `vat_exempt_text` — add a third branch for
  standard VAT (show VAT ID, tax rate, no exemption note)
- Default `tax_rate` (19%) on the invoice form for `standard_vat` practices

#### VAT advance payment report (Umsatzsteuervoranmeldung) — does not exist yet
- No code currently aggregates `tax_amount` for a filing period — unsurprising,
  since neither existing practice charges VAT
- `tax_amount` is already stored per invoice, so this is a groupby-and-sum, not
  new plumbing
- Open design question: cash-basis (Ist-Versteuerung, via `paid_date`) vs.
  accrual (Soll, via `invoice_date`) — `RevenueCalculator` already supports both
  via its `use_paid_date` switch, so this reuses existing infrastructure rather
  than inventing a new one

---

## Open Questions
- Phase 1: exact `InvoiceItem.clean()` validation wording for "must have session
  XOR description"
- Phase 2: cash vs. accrual VAT reporting basis — needs a real decision before
  building the advance-payment report, not just at implementation time
- Phase 2: exact trigger point — build ahead of the Finanzamt conversation, or
  only once the new registration is confirmed?

## Non-Goals (for now)
- Phase 2 (VAT treatment field, advance-payment report) stays undesigned in
  detail until the Kleinunternehmer election is actually dropped — no point
  guessing at the reporting mechanics a year early
- No migration/UI work starts until the IT practice's first invoice is actually
  being drafted
