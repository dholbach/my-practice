# P-043: Bank Statement Import (CSV)

**Status**: ✅ DONE
**Priority**: HIGH
**Effort**: ~12h (MVP + iterations)
**Created**: 2. Februar 2026
**Completed**: 3. Februar 2026

---

## 📋 Overview

**Goal**: Automate payment reconciliation by importing bank statements and matching transactions to invoices.

**Problem**:
- Manual payment tracking is time-consuming
- Need to cross-reference bank statements with invoice list
- Some clients use different names or forget invoice numbers
- Amount discrepancies need manual checking

**Solution**:
- CSV import from GLS Bank statements
- Automatic invoice number extraction from Verwendungszweck
- Fuzzy matching for unclear cases
- Manual review UI for unmatched transactions

---

## 🎯 Scope

### Phase 1: MVP (10-12h)

**Features:**
1. **CSV Parser** (2-3h)
   - Read GLS Bank CSV format (semicolon-delimited, UTF-8)
   - Parse German decimals (90,00 → 90.00)
   - Parse dates (DD.MM.YYYY → YYYY-MM-DD)
   - Filter positive amounts only (income transactions)

2. **Invoice Number Extraction** (2-3h)
   - Pattern 1: Direct codes `LI-3`, `PC-19`, `JC-18`
   - Pattern 2: With keywords `Rechnung Nr. OW-1`, `Invoice No. EC-9`
   - Pattern 3: In context `3x Therapie JL-3`, `ReNr CG-25`
   - Regex patterns:
     ```python
     r'\b([A-Z]{2,4}-\d+)\b'  # Direct
     r'(?:Rechnung|Invoice|ReNr|Re)\s*(?:Nr\.?|No\.?)?\s*([A-Z]{2,4}-\d+)'  # Keywords
     r'Therapie\s+([A-Z]{2,4}-\d+)'  # Context
     ```

3. **Auto-Match Engine** (3-4h)
   - Find invoice by extracted number
   - Verify amount matches **exactly** (no tolerance)
   - Fuzzy name matching with alias system (handle name variations, parent payments, legal name changes)
   - Check invoice status = "sent" (not already paid)
   - Update: `paid_date = Buchungstag`, `status = "paid"`
   - Log match confidence (exact/fuzzy/manual)

4. **Manual Review UI** (3-4h)
   - Table: Unmatched transactions
   - Columns: Date, Name, Verwendungszweck, Amount, Match Status
   - Actions:
     - Dropdown: Select invoice from unpaid list
     - "Mark as Paid" button
     - "Ignore" button (expense/withdrawal/duplicate)
   - Filter: Show only unmatched / Show all
   - Success summary: "X of Y automatically matched, Z require review"

### Phase 2: Enhancements (Future)

**Nice to Have:**
- Fuzzy client name matching (Levenshtein distance)
- CAMT.052 XML support (standardized format)
- Bulk import for multiple months
- Expense auto-categorization (negative amounts → CompanyExpense)
- Match confidence scoring (exact/high/medium/low)
- Duplicate detection (same amount + date + client)

---

## ✅ Implementation Summary

**Completed**: 3. Februar 2026 (12h total effort)

### What Was Built

1. **CSV Import Pipeline**
   - GLS Bank format parser (semicolon, UTF-8, German decimals)
   - BankTransaction model with unique constraint
   - Duplicate detection (practice + date + amount + reference)
   - Auto-ignore self-payments (Einlagen from practice.name)

2. **Smart Matching System**
   - 3 regex patterns: direct (`LI-3`), keyword (`Rechnung Nr. OW-1`), context (`3x Therapie JL-3`)
   - ±5€ tolerance for amount matching
   - Confidence levels: exact, fuzzy, manual, ignored, unmatched
   - ClientAlias model for name variations

3. **Manual Review Interface**
   - Three action modes:
     - **Auto-match** (green): Suggested unpaid invoice, one-click approval
     - **Confirm-paid** (orange): Already-paid invoice, verify duplicate payment
     - **Manual** (dropdown): Select from all unpaid invoices
   - Multi-select support for bulk payments (Sammelzahlungen)
   - Invoice dropdown: `LI-3 (2025-12-15): 90,00 €` format
   - Auto-scroll to next transaction after action
   - ClientAlias checkbox (auto-create for future matches)

4. **Management Commands**
   - `resetinvoices --count=30 --yes`: Reset paid → sent for testing
   - `clearbanktransactions --yes --all`: Delete transactions for reimport

5. **Navigation Integration**
   - Badge in nav menu showing unmatched count (excludes ignored)
   - Dashboard reminder widget when transactions need attention

### Key Features

- **Bulk Payments**: Select multiple invoices for single transaction
  - Notes: "Sammelzahlung für: LI-3, OW-1, JL-2"
  - All invoices marked as paid with same date

- **Auto-Ignore**: Self-payments automatically set to `ignored`
  - Note: "Eigene Zahlung (Einlage) - automatisch ignoriert"

- **Privacy Mode**: Payer names wrapped in `sensitive-data` CSS class

### Testing Results

- Successfully imported June 2025 onwards (~6 months of data)
- Minimal manual intervention required
- Auto-match worked for majority of transactions
- Edge cases (bulk payments, self-payments) handled correctly

### Commits

- `09bfcae`: Auto-ignore practitioner self-payments
- `d12463e`: Improved invoice dropdown (date + amount)
- `5d2dff8`: Multi-select for bulk payments
- Plus 8 bug fix commits during testing phase

---

## 🗂️ File Structure

```
app/my_practice/
├── models/
│   └── bank_statement.py (new)  # BankTransaction model
├── utils/
│   └── bank_import.py (new)     # BankStatementImporter class
├── forms/
│   └── bank_import_forms.py (new)  # CSV upload form
├── views/
│   └── bank_import_views.py (new)  # Import + review views
└── templates/
    └── my_practice/
        ├── bank_import.html (new)
        └── bank_review.html (new)
```

---

## 💾 Database Model

```python
class BankTransaction(models.Model):
    """Bank statement transaction"""

    practice = models.ForeignKey("Practice", on_delete=models.CASCADE)

    # CSV Fields
    transaction_date = models.DateField("Buchungstag")
    value_date = models.DateField("Valutadatum")
    payer_name = models.CharField(max_length=200, "Name Zahlungsbeteiligter")
    payer_iban = models.CharField(max_length=34, blank=True)
    reference = models.TextField("Verwendungszweck")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)

    # Matching
    matched_invoice = models.ForeignKey(
        "Invoice",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bank_transactions"
    )
    match_confidence = models.CharField(
        max_length=20,
        choices=[
            ("exact", "Exact Match"),
            ("fuzzy", "Fuzzy Match"),
            ("manual", "Manual Assignment"),
            ("ignored", "Ignored"),
            ("unmatched", "Unmatched"),
        ],
        default="unmatched"
    )
    extracted_invoice_number = models.CharField(max_length=20, blank=True)

    # Metadata
    imported_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [["practice", "transaction_date", "amount", "reference"]]
        ordering = ["-transaction_date"]
```

---

## 🔧 Implementation Steps

### Step 1: Model + Migration (30min)
```bash
# Create model
touch app/my_practice/models/bank_statement.py

# Add to models/__init__.py
from .bank_statement import BankTransaction

# Create migration
./dev.py manage makemigrations
./dev.py manage migrate
```

### Step 2: CSV Parser (2-3h)
```python
# app/my_practice/utils/bank_import.py

import csv
import re
from decimal import Decimal
from datetime import datetime

class BankStatementImporter:
    """Import and match GLS Bank CSV statements"""

    INVOICE_PATTERNS = [
        r'\b([A-Z]{2,4}-\d+)\b',  # Direct: LI-3
        r'(?:Rechnung|Invoice|ReNr|Re)\s*(?:Nr\.?|No\.?)?\s*([A-Z]{2,4}-\d+)',
        r'Therapie\s+([A-Z]{2,4}-\d+)',
    ]

    def __init__(self, csv_file, practice):
        self.csv_file = csv_file
        self.practice = practice
        self.results = {
            "total": 0,
            "matched": 0,
            "unmatched": 0,
            "ignored": 0,
            "errors": [],
        }

    def parse_csv(self):
        """Parse GLS Bank CSV format"""
        # TODO: Implement parsing logic
        pass

    def extract_invoice_number(self, verwendungszweck):
        """Extract invoice number from reference text"""
        for pattern in self.INVOICE_PATTERNS:
            match = re.search(pattern, verwendungszweck, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return None

    def match_transaction(self, transaction):
        """Match transaction to invoice with exact amount and fuzzy name"""
        # Extract invoice number from reference
        invoice_number = self.extract_invoice_number(transaction['reference'])
        if not invoice_number:
            return None

        # Find invoice with exact amount match
        invoice = Invoice.objects.filter(
            invoice_number=invoice_number,
            total_amount=transaction['amount'],
            status='sent'
        ).first()

        # Fuzzy name matching via ClientAlias if no direct match
        if not invoice:
            alias = ClientAlias.objects.filter(
                alias_name__iexact=transaction['payer_name']
            ).first()
            if alias:
                invoice = Invoice.objects.filter(
                    invoice_number=invoice_number,
                    client=alias.client,
                    total_amount=transaction['amount'],
                    status='sent'
                ).first()

        return invoice

    def process(self):
        """Process entire CSV file"""
        # TODO: Main processing loop
        pass
```

### Step 3: Import View (2h)
- Upload form (CSV file input)
- Preview parsed transactions (first 10 rows)
- "Process Import" button
- Success/error feedback

### Step 4: Review View (2-3h)
- Table of unmatched transactions
- Dropdown to select invoice
- Match confirmation with amount comparison
- Bulk actions (ignore multiple)

### Step 5: Tests (1-2h)
```python
# tests/test_bank_import.py

class BankImportTestCase(TestCase):
    def test_parse_gls_csv(self):
        """Test CSV parsing"""
        pass

    def test_extract_invoice_number_direct(self):
        """Test pattern: LI-3"""
        pass

    def test_extract_invoice_number_keyword(self):
        """Test pattern: Rechnung Nr. OW-1"""
        pass

    def test_match_exact_amount(self):
        """Test exact amount match - no tolerance"""
        pass

    def test_fuzzy_name_matching_via_alias(self):
        """Test name matching through ClientAlias"""
        pass

    def test_match_with_tolerance(self):
        """Test ±5€ tolerance"""
        pass

    def test_ignore_negative_amounts(self):
        """Test expense filtering"""
        pass
```

---

## 📊 Sample Data (from provided CSV)

**Perfect Matches:**
- `LI-3` → 90,00€ → "Adam Smith"
- `OW-1` → 180,00€ → "Rechnung Nr. OW-1"
- `EC-9` → 160,00€ → "Invoice No. EC-9"

**Fuzzy Matches:**
- `JL-3` → 270,00€ → "3x Therapie JL-3" (context pattern)
- `PB-12` → 80,00€ → "Re Nr PB-12 vom 21.12.25" (keyword variant)

**Problematic Cases:**
- `Mi 9-10` → 400,00€ → "Maria Musterfrau" (no invoice number)
- Multiple invoices: "For invoices 29 and 30" (Benjamin Kahn)

**To Ignore:**
- `-300,00€` → "Miete Lenbach 16" (expense - negative)
- `-350,00€` → "Entnahme / Unternehmerlohn" (withdrawal - negative)
- `-4,99€` → "klarmobil GmbH" (expense - negative)

---

## 🎨 UI Mockup

### Import Page
```
┌─────────────────────────────────────────────┐
│ Bank Statement Import                        │
├─────────────────────────────────────────────┤
│                                              │
│ 1. Upload CSV File                           │
│    [Choose File] No file chosen              │
│    Supported: GLS Bank CSV (semicolon)       │
│                                              │
│ 2. Preview (first 10 transactions)           │
│    ┌──────────────────────────────────────┐ │
│    │ Date       | Name        | Amount    │ │
│    │ 02.02.2026 | Adam  Smith | 90,00 €  │ │
│    │ 02.02.2026 | M.Musterfrau| 400,00 € │ │
│    └──────────────────────────────────────┘ │
│                                              │
│ [Process Import]                             │
│                                              │
└─────────────────────────────────────────────┘
```

### Review Page
```
┌─────────────────────────────────────────────┐
│ Bank Import Results                          │
├─────────────────────────────────────────────┤
│                                              │
│ ✓ 15 automatically matched                   │
│ ⚠️  3 require manual review                  │
│ ➖ 5 ignored (expenses)                       │
│                                              │
│ Unmatched Transactions:                      │
│ ┌──────────────────────────────────────────┐│
│ │Date       │Name        │Ref     │Amount  ││
│ │02.02.2026 │M.Musterfrau│Mi 9-10 │400,00€ ││
│ │           │[Select Invoice ▼] [Match]    ││
│ ├──────────────────────────────────────────┤│
│ │23.01.2026 │MATS        │KK1     │210,00€ ││
│ │           │[Select Invoice ▼] [Match]    ││
│ └──────────────────────────────────────────┘│
│                                              │
│ [Back to Dashboard]                          │
│                                              │
└─────────────────────────────────────────────┘
```

---

## ✅ Acceptance Criteria

1. **CSV Upload**: Accept GLS Bank CSV files (UTF-8, semicolon-delimited)
2. **Parsing**: Correctly parse dates, amounts, names, references
3. **Invoice Extraction**: Detect invoice numbers in 80%+ of cases
4. **Auto-Match**: Match transactions with ±5€ tolerance
5. **Update Invoices**: Set `paid_date` and `status="paid"` on match
6. **Manual Review**: Provide UI for unmatched transactions
7. **Expense Filtering**: Ignore negative amounts (expenses/withdrawals)
8. **No Duplicates**: Prevent re-importing same transactions
9. **Tests**: 90%+ coverage for matching logic
10. **Performance**: Process 100 transactions in <2 seconds

---

## 🚀 Future Enhancements

- **CAMT.052 Support**: Standardized XML format (all German banks)
- **Fuzzy Name Matching**: Levenshtein distance for client names
- **Multi-Month Import**: Bulk process 3-6 months of statements
- **Expense Auto-Categorization**: Map negative transactions to CompanyExpense
- **Dashboard Widget**: "Unmatched Transactions" badge
- **Notification**: Email when unmatched transactions > 5
- **API Integration**: Direct bank API connection (PSD2/Open Banking)
- **Reconciliation Report**: Monthly payment overview PDF

---

## 📚 Resources

**Documentation:**
- GLS Bank CSV Format: [Example provided]
- CAMT.052 Specification: ISO 20022
- PSD2 Open Banking: For future API integration

**Libraries:**
- `csv` (stdlib): CSV parsing
- `re` (stdlib): Pattern matching
- `Levenshtein` (optional): Fuzzy string matching
- `lxml` (optional): XML parsing for CAMT.052

**Similar Projects:**
- German accounting software (lexoffice, sevDesk)
- Open Banking integrations (FinAPI, Tink)

---

## 🎯 Success Metrics

- **Automation Rate**: 80%+ transactions auto-matched
- **Time Savings**: 15-30 minutes per month saved
- **Accuracy**: 99%+ correct matches
- **User Satisfaction**: Reduced manual payment tracking effort

---

## 📝 Notes

- Start with CSV MVP, add CAMT.052 later if needed
- Focus on positive amounts (income) first
- Keep manual override for edge cases
- Consider multi-bank support in future (different CSV formats)
