"""Shared fixtures for the bank import and review view tests."""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase

from ..models import (
    InvoiceItem,
    Practice,
    ServiceType,
    Session,
    UserPractice,
    allow_issued_invoice_writes,
)
from .test_helpers import select_practice

PRACTICE_IBAN = "DE89370400440532013000"


@allow_issued_invoice_writes()
def make_invoice_item(invoice, practice, client_obj, rate=Decimal("90.00")):
    """Create the minimum supporting objects for an InvoiceItem."""
    service_type, _ = ServiceType.objects.get_or_create(
        code="test_therapy_60",
        defaults={"practice": practice, "name": "Therapy 60min"},
    )
    session = Session.objects.create(
        client=client_obj,
        session_date=date(2026, 1, 1),
        duration=60,
    )
    return InvoiceItem.objects.create(
        invoice=invoice,
        service_type=service_type,
        session=session,
        rate=rate,
        quantity=1,
    )


def csv_bytes(rows, iban=PRACTICE_IBAN):
    header = (
        "IBAN Auftragskonto;Buchungstag;Valutadatum;"
        "Name Zahlungsbeteiligter;IBAN Zahlungsbeteiligter;"
        "Betrag;Saldo nach Buchung;Verwendungszweck"
    )
    lines = [header]
    lines.extend(
        ";".join(
            [
                iban,
                r.get("date", "15.01.2026"),
                r.get("date", "15.01.2026"),
                r.get("payer", "Test Zahler"),
                r.get("payer_iban", ""),
                r.get("amount", "90,00"),
                "1000,00",
                r.get("ref", "Test"),
            ]
        )
        for r in rows
    )
    return "\n".join(lines).encode("utf-8")


class BankImportViewBase(TestCase):
    """Shared setUp for bank import view tests."""

    def setUp(self):
        self.user = User.objects.create_user(username="bankuser", password="pass")
        self.practice = Practice.objects.create(
            name="Test Praxis",
            slug="bank-import-views",
            title="Therapeutin",
            email="test@example.com",
            iban=PRACTICE_IBAN,
        )
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)

        self.http = TestClient()
        self.http.login(username="bankuser", password="pass")
        select_practice(self.http, self.practice)
