# ADR-0007: Issued invoices are kept ten years, not eight

## Context

Since #491 an issued invoice cannot be deleted until the end of the tenth
calendar year after its date (`INVOICE_RETENTION_YEARS` in
[`models/invoice.py`](../../app/my_practice/models/invoice.py), enforced by the
`pre_delete` signal in [`signals.py`](../../app/my_practice/signals.py)). The
same period gates deleting a client who still has invoices
(`views/client_views.py`).

At the time that was written, § 147 AO required ten years for invoices. Since
1 January 2025 (Bürokratieentlastungsgesetz IV) the period for accounting
vouchers (*Buchungsbelege*), invoices included, is eight years; books, annual
financial statements and similar records stay at ten. So the constant is now
longer than the law strictly asks for invoices, and a tidy-up that "corrects"
it to 8 looks reasonable.

## Decision

**Keep ten years.** The practice owner decided this explicitly (2026-10-14)
rather than leave it to whoever reads the AO next.

- The two errors are not symmetric. Keeping an invoice two years too long
  costs a few database rows. Deleting it too early cannot be undone and may
  breach a retention duty — for example if the transition rules, a tax audit
  in progress, or a reading of an invoice as part of the books keep the longer
  period alive for that record.
- One period for invoices and the client records they belong to
  (`GDPR_RETENTION_YEARS`, also ten) means a client and their invoices become
  deletable together, instead of invoices outliving the client file or the
  reverse.

## Consequences

- Do not lower `INVOICE_RETENTION_YEARS` to match § 147 AO. Changing it is a
  decision for the practice owner (and their tax advisor), recorded in a new ADR.
- If a self-hoster needs a different period, make it a per-practice setting
  defaulting to ten, rather than changing the constant for everyone.
- User-facing texts may keep citing § 147 AO as the reason invoices are
  retained; the period itself is this decision.
