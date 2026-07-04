"""
Bank statement import and matching utilities.

Handles CSV parsing, invoice number extraction, and automatic payment matching.
"""

import csv
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from ..models import (
    BankTransaction,
    ClientAlias,
    CompanyExpense,
    CompanyWithdrawal,
    Invoice,
)


class BankStatementImporter:
    """
    Import and match bank transactions from CSV files.

    Built for GLS Bank's CSV export format (semicolon-delimited). Other banks
    may work if their export uses the same column names (Buchungstag, Valutadatum,
    Name Zahlungsbeteiligter, IBAN Zahlungsbeteiligter, Verwendungszweck, Betrag,
    Saldo nach Buchung, IBAN Auftragskonto) but this is untested. To support a
    different bank format, subclass and override parse_csv_row().

    Format details:
    - Encoding: UTF-8
    - Delimiter: Semicolon (;)
    - Decimal separator: Comma (,)
    - Date format: DD.MM.YYYY

    Usage:
        importer = BankStatementImporter(csv_file, practice)
        results = importer.process()
    """

    # Invoice number extraction patterns (priority order)
    INVOICE_PATTERNS = [
        # Pattern 1: Direct codes (XX-1, YY-2, AB-3)
        r"\b([A-Z]{2,4}-\d+)\b",
        # Pattern 2: With keywords (Rechnung Nr. YY-2, Invoice No. AB-3)
        r"(?:Rechnung|Invoice|ReNr|Re)\s*(?:Nr\.?|No\.?)?\s*([A-Z]{2,4}-\d+)",
        # Pattern 3: In context (3x Therapie CD-4)
        r"Therapie\s+([A-Z]{2,4}-\d+)",
    ]

    # Keywords for salary / owner-pay withdrawal detection
    WITHDRAWAL_KEYWORDS = [
        "entnahme",
        "unternehmerlohn",
        "payr",
        "gehalt",
    ]

    # Keywords for correction / reversal detection
    CORRECTION_KEYWORDS = [
        "fehlbuchung",
        "korrektur",
        "storno",
        "rückbuchung",
        "ausgleich",
    ]

    @staticmethod
    def _normalize_iban(iban: str) -> str:
        """Normalize IBAN by removing spaces and uppercasing."""
        return iban.replace(" ", "").upper()

    def __init__(self, csv_file, practice):
        """
        Initialize importer.

        Args:
            csv_file: File object with CSV content
            practice: Practice instance for scoping
        """
        self.csv_file = csv_file
        self.practice = practice
        # Normalized private IBAN for withdrawal/contribution detection
        self.private_iban = (
            self._normalize_iban(practice.private_bank_account)
            if practice.private_bank_account
            else ""
        )
        # IBAN of the source account from the CSV (populated during process())
        self.account_iban: str = ""
        self.results: dict[str, Any] = {
            "total": 0,
            "matched": 0,
            "unmatched": 0,
            "needs_review": 0,
            "ignored": 0,
            "errors": [],
            "transactions": [],
        }

    def parse_german_decimal(self, value: str) -> Decimal:
        """
        Parse German decimal format to Decimal.

        Args:
            value: String like "90,00" or "-300,00"

        Returns:
            Decimal object

        Raises:
            InvalidOperation: If parsing fails
        """
        # Replace comma with dot for Decimal parsing
        normalized = value.replace(",", ".")
        return Decimal(normalized)

    def parse_german_date(self, value: str) -> "date":
        """
        Parse German date format to datetime.

        Args:
            value: String like "02.02.2026"

        Returns:
            datetime.date object

        Raises:
            ValueError: If parsing fails
        """
        return datetime.strptime(value, "%d.%m.%Y").date()

    def extract_invoice_number(self, reference: str) -> str | None:
        """
        Extract invoice number from reference text using regex patterns.

        Args:
            reference: Payment reference text (Verwendungszweck)

        Returns:
            Extracted invoice number (uppercase) or None

        Examples:
            "XX-1" → "XX-1"
            "Rechnung Nr. YY-2" → "YY-2"
            "3x Therapie CD-4" → "CD-4"
            "Mi 9-10" → None
        """
        for pattern in self.INVOICE_PATTERNS:
            match = re.search(pattern, reference, re.IGNORECASE)
            if match:
                # Extract captured group and normalize to uppercase
                invoice_number = match.group(1).upper()
                return invoice_number
        return None

    def find_matching_invoice(
        self, invoice_number: str, amount: Decimal, payer_name: str
    ) -> tuple[Invoice, str] | None:
        """
        Find invoice matching the extracted number and amount exactly.

        Uses fuzzy name matching via ClientAlias for name variations
        (parent payments, legal name changes, bank account differences).

        Args:
            invoice_number: Extracted invoice number
            amount: Transaction amount (must match exactly)
            payer_name: Name from bank statement

        Returns:
            Tuple of (Invoice, confidence) or None
            Confidence values: "exact" (direct match), "fuzzy" (via alias)
        """
        try:
            # Find invoice by number with exact amount
            invoice = Invoice.objects.filter(
                practice=self.practice,
                invoice_number=invoice_number,
                status="sent",  # Only match unpaid invoices
            ).first()

            if not invoice:
                return None

            # Calculate invoice total
            invoice_total = invoice.calculate_total()

            # Require exact amount match (no tolerance)
            if abs(invoice_total - amount) >= Decimal("0.01"):
                return None

            # Direct match
            if invoice.client.full_name.lower() == payer_name.lower():
                return (invoice, "exact")

            # Fuzzy match via ClientAlias
            alias = ClientAlias.objects.filter(
                client=invoice.client, alias_name__iexact=payer_name
            ).first()

            if alias:
                return (invoice, "fuzzy")

            # Amount matches but name doesn't - still return as exact
            # (user can create alias if needed)
            return (invoice, "exact")

        except Invoice.MultipleObjectsReturned:
            # Should not happen with unique invoice_number
            return None

    def detect_and_create_financial_record(
        self, transaction_date, amount, reference, payer_iban: str = ""
    ) -> dict | None:
        """
        Detect if a negative transaction is a withdrawal or expense and create it.

        Detection priority and category assignment:
        - IBAN match + correction keywords → CompanyWithdrawal(correction)
        - IBAN match + salary keywords    → CompanyWithdrawal(salary)
        - IBAN match, no keywords         → CompanyWithdrawal(private_transfer)
        - No IBAN configured, correction keywords → CompanyWithdrawal(correction)
        - No IBAN configured, salary keywords    → CompanyWithdrawal(salary)
        - Otherwise                              → CompanyExpense(other)

        Args:
            transaction_date: Date of transaction
            amount: Transaction amount (negative)
            reference: Transaction reference text
            payer_iban: IBAN of the counterparty (recipient for outgoing payments)

        Returns:
            Dictionary with type and created record, or None if not auto-created
        """
        reference_lower = reference.lower()
        abs_amount = abs(amount)

        # IBAN-based detection: if the private account is configured and the
        # transaction goes to/from it (via payer_iban field OR mention in reference
        # text), it's treated as a private-account transaction.
        iban_match = bool(
            self.private_iban
            and (
                self._normalize_iban(payer_iban) == self.private_iban
                or self.private_iban in self._normalize_iban(reference)
            )
        )

        # Keyword sub-classification — used to assign category regardless of how
        # the withdrawal was detected (IBAN or fallback).
        salary_keyword_hit = any(keyword in reference_lower for keyword in self.WITHDRAWAL_KEYWORDS)
        correction_keyword_hit = any(
            keyword in reference_lower for keyword in self.CORRECTION_KEYWORDS
        )

        # Keyword fallback: only fires when no private IBAN is configured, to avoid
        # false positives on client payments that mention salary-related words.
        keyword_match = not self.private_iban and (salary_keyword_hit or correction_keyword_hit)

        is_withdrawal = iban_match or keyword_match

        if is_withdrawal:
            # Check if withdrawal already exists
            existing_withdrawal = CompanyWithdrawal.objects.filter(
                practice=self.practice,
                date=transaction_date,
                amount=abs_amount,
                description=reference,
            ).first()

            if existing_withdrawal:
                return {"type": "CompanyWithdrawal", "record": existing_withdrawal}

            # Category priority:
            # 1. Correction keywords (fehlbuchung/storno) → correction
            # 2. Salary keywords (entnahme/gehalt) → salary
            # 3. IBAN match only (pure capital transfer, no keywords) → private_transfer
            if correction_keyword_hit:
                withdrawal_category = "correction"
            elif salary_keyword_hit:
                withdrawal_category = "salary"
            else:
                withdrawal_category = "private_transfer"
            withdrawal = CompanyWithdrawal.objects.create(
                practice=self.practice,
                date=transaction_date,
                amount=abs_amount,
                description=reference,
                category=withdrawal_category,
            )
            return {"type": "CompanyWithdrawal", "record": withdrawal}
        else:
            # Check if expense already exists
            existing_expense = CompanyExpense.objects.filter(
                practice=self.practice,
                date=transaction_date,
                amount=abs_amount,
                description=reference,
            ).first()

            if existing_expense:
                return {"type": "CompanyExpense", "record": existing_expense}

            # Create CompanyExpense for other negative amounts
            expense = CompanyExpense.objects.create(
                practice=self.practice,
                date=transaction_date,
                amount=abs_amount,
                description=reference,
                category="other",
                has_invoice=False,
                is_tax_deductible=True,
            )
            return {"type": "CompanyExpense", "record": expense}

    def parse_csv_row(self, row: dict[str, str]) -> dict | None:
        """
        Parse a single CSV row into transaction data.

        Args:
            row: Dictionary with CSV column headers as keys

        Returns:
            Dictionary with parsed transaction data or None if parsing fails
        """
        try:
            return {
                "transaction_date": self.parse_german_date(row["Buchungstag"]),
                "value_date": self.parse_german_date(row["Valutadatum"]),
                "payer_name": row["Name Zahlungsbeteiligter"],
                "payer_iban": row.get("IBAN Zahlungsbeteiligter", ""),
                "reference": row["Verwendungszweck"],
                "amount": self.parse_german_decimal(row["Betrag"]),
                "balance_after": self.parse_german_decimal(row["Saldo nach Buchung"]),
            }
        except KeyError, ValueError, InvalidOperation:
            return None

    def _validate_csv_account(self, rows: list) -> bool:
        """Verify the CSV belongs to this practice's bank account. Returns False and sets error if mismatch."""
        if not rows:
            return True
        csv_account_iban = rows[0].get("IBAN Auftragskonto", "").strip()
        self.account_iban = csv_account_iban
        practice_iban_norm = self._normalize_iban(self.practice.iban)
        csv_iban_norm = self._normalize_iban(csv_account_iban)
        if csv_iban_norm and practice_iban_norm and csv_iban_norm != practice_iban_norm:
            self.results["errors"].append(
                f"Falsches Konto: Die CSV-Datei gehört zu IBAN {csv_account_iban}, "
                f"erwartet wird die Praxis-IBAN {self.practice.iban}. "
                "Import abgebrochen."
            )
            self.results["account_mismatch"] = True
            return False
        return True

    def _handle_negative_row(self, parsed: dict, skip_negatives: bool) -> bool:
        """Handle a negative-amount row. Returns True if fully processed (caller should continue)."""
        existing = BankTransaction.objects.filter(
            practice=self.practice,
            transaction_date=parsed["transaction_date"],
            amount=parsed["amount"],
            reference=parsed["reference"],
        ).first()
        if existing:
            self.results["ignored"] += 1
            return True

        withdrawal_or_expense = self.detect_and_create_financial_record(
            parsed["transaction_date"],
            parsed["amount"],
            parsed["reference"],
            payer_iban=parsed["payer_iban"],
        )
        if withdrawal_or_expense:
            record_type = withdrawal_or_expense["type"]
            record = withdrawal_or_expense["record"]
            if record_type == "CompanyWithdrawal":
                match_confidence, linked_expense, linked_withdrawal = (
                    "auto-withdrawal",
                    None,
                    record,
                )
            else:
                match_confidence, linked_expense, linked_withdrawal = "auto-expense", record, None
            BankTransaction.objects.create(
                practice=self.practice,
                transaction_date=parsed["transaction_date"],
                value_date=parsed["value_date"],
                payer_name=parsed["payer_name"],
                payer_iban=parsed["payer_iban"],
                reference=parsed["reference"],
                amount=parsed["amount"],
                balance_after=parsed["balance_after"],
                account_iban=self.account_iban,
                match_confidence=match_confidence,
                linked_expense=linked_expense,
                linked_withdrawal=linked_withdrawal,
                notes=f"Auto-created {record_type}: {record}",
                processed=record_type == "CompanyWithdrawal",
            )
            self.results["needs_review"] += 1
            return True

        if skip_negatives:
            self.results["ignored"] += 1
            return True

        return False

    def _classify_transaction(
        self,
        parsed: dict,
        is_private_contribution: bool,
        is_self_payment: bool,
        invoice_number: str | None,
    ) -> tuple[str, str, Invoice | None, CompanyWithdrawal | None]:
        """Classify a transaction and update result counters. Returns (confidence, notes, matched_invoice, linked_withdrawal)."""
        confidence = "unmatched"
        notes = ""
        linked_withdrawal = None
        matched_invoice = None

        if is_private_contribution:
            reference_lower = parsed["reference"].lower()
            correction_keyword_hit = any(kw in reference_lower for kw in self.CORRECTION_KEYWORDS)
            # Positive transactions from private IBAN with a correction keyword
            # (e.g. "Fehlbuchung") are bank errors, not real contributions.
            if correction_keyword_hit:
                withdrawal_category = "correction"
                confidence = "auto-correction"
                notes = "Fehlbuchung / Korrektur vom privaten Konto"
            else:
                withdrawal_category = "contribution"
                confidence = "auto-contribution"
                notes = "Kapitaleinlage vom privaten Konto"
            # Only create for positive (incoming) amounts
            if parsed["amount"] > 0:
                withdrawal, _ = CompanyWithdrawal.objects.get_or_create(
                    practice=self.practice,
                    date=parsed["transaction_date"],
                    amount=parsed["amount"],
                    description=parsed["reference"],
                    defaults={"category": withdrawal_category},
                )
                linked_withdrawal = withdrawal
            self.results["needs_review"] += 1
        elif is_self_payment:
            confidence = "ignored"
            notes = "Eigene Zahlung (Einlage) - automatisch ignoriert"
            self.results["ignored"] += 1
        elif invoice_number:
            match_result = self.find_matching_invoice(
                invoice_number, parsed["amount"], parsed["payer_name"]
            )
            if match_result:
                matched_invoice, confidence = match_result
                self.results["matched"] += 1
            else:
                self.results["unmatched"] += 1
        else:
            self.results["unmatched"] += 1

        return confidence, notes, matched_invoice, linked_withdrawal

    @transaction.atomic
    def process(self, skip_negatives: bool = True) -> dict[str, Any]:
        """
        Process CSV file and match transactions to invoices.

        Args:
            skip_negatives: If True, ignore negative amounts (expenses)

        Returns:
            Dictionary with processing results
        """
        content = self.csv_file.read().decode("utf-8")
        rows = list(csv.DictReader(content.splitlines(), delimiter=";"))

        if not self._validate_csv_account(rows):
            return self.results

        for row in rows:
            self.results["total"] += 1

            parsed = self.parse_csv_row(row)
            if not parsed:
                self.results["errors"].append(f"Failed to parse row: {row}")
                continue

            payer_name_lower = parsed["payer_name"].lower().strip()
            is_self_payment = payer_name_lower == self.practice.name.lower().strip()

            # IBAN-based capital contribution detection takes priority over name matching.
            # Check both the payer_iban field AND the reference text (bank embeds IBANs there).
            payer_iban_normalized = self._normalize_iban(parsed["payer_iban"])
            reference_normalized = self._normalize_iban(parsed["reference"])
            is_private_contribution = bool(
                self.private_iban
                and (
                    payer_iban_normalized == self.private_iban
                    or self.private_iban in reference_normalized
                )
            )

            if parsed["amount"] < 0 and self._handle_negative_row(parsed, skip_negatives):
                continue

            # Duplicate check for non-negative (and unhandled negative) rows
            existing = BankTransaction.objects.filter(
                practice=self.practice,
                transaction_date=parsed["transaction_date"],
                amount=parsed["amount"],
                reference=parsed["reference"],
            ).first()
            if existing:
                self.results["ignored"] += 1
                continue

            invoice_number = self.extract_invoice_number(parsed["reference"])
            confidence, notes, matched_invoice, linked_withdrawal = self._classify_transaction(
                parsed, is_private_contribution, is_self_payment, invoice_number
            )

            bank_transaction = BankTransaction.objects.create(
                practice=self.practice,
                transaction_date=parsed["transaction_date"],
                value_date=parsed["value_date"],
                payer_name=parsed["payer_name"],
                payer_iban=parsed["payer_iban"],
                reference=parsed["reference"],
                amount=parsed["amount"],
                balance_after=parsed["balance_after"],
                account_iban=self.account_iban,
                matched_invoice=matched_invoice,
                match_confidence=confidence,
                extracted_invoice_number=invoice_number or "",
                linked_withdrawal=linked_withdrawal,
                notes=notes,
                processed=matched_invoice is not None,
            )

            if matched_invoice:
                matched_invoice.status = "paid"
                matched_invoice.paid_date = parsed["transaction_date"]
                matched_invoice.save()

            self.results["transactions"].append(bank_transaction)

        return self.results
