# P-043: Bank Statement Import (CSV)

**Status**: ✅ DONE
**Completed**: 3 Feb 2026 (MVP), extended significantly since

## What Was Built

Automates payment reconciliation: import a bank CSV, auto-match transactions
to invoices by extracted invoice number + amount, and review the rest by hand.

- `BankTransaction` model (`models/bank_statement.py`) — one row per statement
  line, with a `Confidence` enum (`exact`/`fuzzy`/`manual`/`ignored`/
  `unmatched`, plus auto-created withdrawal/expense/contribution/correction
  states added after the MVP)
- `BankStatementImporter` (`utils/bank_import.py`) — CSV parsing with
  delimiter/columns configurable per practice (the original MVP was
  GLS-Bank-specific; this was later generalized)
- Invoice-number extraction via regex (direct code, keyword-prefixed, or
  in-context), ±5€ amount tolerance, and `ClientAlias`-based name matching for
  payers whose bank name doesn't match the client record
- Manual review UI (`bank_import_views.py`, `bank_review.html`) with
  auto-match/confirm-paid/manual-select actions, multi-select for bulk
  payments (Sammelzahlungen), and auto-ignore for the practitioner's own
  transfers
- Dashboard/nav badge showing the unmatched-transaction count

## Not Built

CAMT.052 XML support, direct bank API integration (PSD2/Open Banking), and a
dedicated reconciliation PDF report were scoped as future enhancements and
never implemented — CSV import via the practice-configurable parser above
turned out to be sufficient.

## Related

- [CODE_STRUCTURE.md](../../architecture/CODE_STRUCTURE.md) — current architecture
- [CLAUDE.md](../../../CLAUDE.md) — Language Policy / privacy conventions used in the review UI
