"""Smoke test for the seed_sample_data management command.

Runs the full generator once — this is intentionally slower than a typical
test (real random session/invoice/note generation for 45 fictional
clients across ~2 years) but it's the only thing that catches "the seed
script no longer runs" before a new contributor's first ./dev.py start.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from ..models import Client, Invoice, Practice, Session
from ..models.gebueh import Leistungserfassung
from ..utils.gebueh_helpers import build_gebueh_blocks, gebueh_total_for_blocks


class SeedSampleDataCommandTests(TestCase):
    def test_seed_then_idempotent_rerun_then_clear(self):
        """One combined test — the full generation pass is the slow part
        (~15-20s), so this exercises seed → idempotency → clear without
        paying that cost three times over for three separate assertions."""
        out = StringIO()
        call_command("seed_sample_data", "--yes", stdout=out)

        practice = Practice.objects.get(slug="demo")
        self.assertGreater(Client.objects.filter(practice=practice).count(), 0)
        self.assertGreater(Session.objects.filter(client__practice=practice).count(), 0)
        self.assertGreater(Invoice.objects.filter(client__practice=practice).count(), 0)
        self.assertIn("Seeded:", out.getvalue())
        client_count = Client.objects.filter(practice__slug="demo").count()

        # Re-running without --clear must detect existing demo data and no-op.
        rerun_out = StringIO()
        call_command("seed_sample_data", "--yes", stdout=rerun_out)
        self.assertIn("already exists", rerun_out.getvalue())
        self.assertEqual(Client.objects.filter(practice__slug="demo").count(), client_count)

        # GebüH demo data: the fee-schedule clients exist and carry service lines,
        # otherwise the invoice-detail breakdown and the client-detail diagnosis
        # callout have nothing to render (both are documented screenshot subjects).
        gebueh_clients = Client.objects.filter(practice=practice, needs_gebueh_invoice=True)
        self.assertEqual(gebueh_clients.count(), 3)
        self.assertGreater(
            Leistungserfassung.objects.filter(session__client__in=gebueh_clients).count(), 0
        )

        # At least one invoice must actually build a non-empty GebüH breakdown.
        with_breakdown = [
            inv
            for inv in Invoice.objects.filter(client__in=gebueh_clients)
            if gebueh_total_for_blocks(build_gebueh_blocks(inv))
        ]
        self.assertTrue(with_breakdown, "no seeded invoice renders a GebüH breakdown")

        # Recorded GebüH amounts never exceed the fee actually charged for the session.
        for invoice in with_breakdown:
            for block in build_gebueh_blocks(invoice):
                self.assertLessEqual(block["gebueh_sum"], block["vereinbarter_betrag"])

        # --clear removes everything it created, including the demo practice itself.
        # Leistungserfassung.session is PROTECT, so this also guards against the
        # GebüH lines blocking session deletion.
        call_command("seed_sample_data", "--clear", "--yes", stdout=StringIO())
        self.assertFalse(Practice.objects.filter(slug="demo").exists())
        self.assertEqual(Client.objects.filter(practice__slug="demo").count(), 0)
        self.assertEqual(Leistungserfassung.objects.count(), 0)
