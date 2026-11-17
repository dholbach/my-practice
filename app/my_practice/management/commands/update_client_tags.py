"""
Management command to update automatic tags for clients.
Run this periodically (e.g., daily) to maintain system tags.
"""

from django.core.management.base import BaseCommand
from django.db.models import Max
from django.utils import timezone

from ...models import Client, ClientTag
from ...models.session import Session
from ...utils.tag_helpers import RECENT_ACTIVITY_WINDOW_DAYS


class Command(BaseCommand):
    help = "Update automatic client tags (no-next-session, incomplete-intake)"

    SYSTEM_TAGS = {
        "no-next-session": {
            "name": "no-next-session",
            "color": "orange",
            "category": "attention",
            "description": "Klient hat keine geplante nächste Sitzung",
            "is_system": True,
        },
        "incomplete-intake": {
            "name": "incomplete-intake",
            "color": "yellow",
            "category": "attention",
            "description": "Aufnahmeprozess noch nicht abgeschlossen",
            "is_system": True,
        },
    }

    def handle(self, *args, **options):
        self.stdout.write("Updating automatic client tags...")
        today = timezone.localdate()

        tags = self._ensure_system_tags()
        future, recent, started = self._session_activity(today)
        totals = {"added": 0, "removed": 0}

        self._strip_inactive_clients(totals)
        self._sync_active_clients(tags, future, recent, started, totals)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted: Added {totals['added']} tags, removed {totals['removed']} tags"
            )
        )

    def _ensure_system_tags(self) -> dict[str, ClientTag]:
        """Create or refresh the system tags, keyed by slug."""
        tags = {}
        for slug, attrs in self.SYSTEM_TAGS.items():
            tag, created = ClientTag.objects.update_or_create(slug=slug, defaults=attrs)
            tags[slug] = tag
            if created:
                self.stdout.write(self.style.SUCCESS(f"  Created system tag: {tag.name}"))
        return tags

    @staticmethod
    def _session_activity(today) -> tuple[set[int], set[int], set[int]]:
        """Ids of active clients with a future session, a recent one, and any session.

        Two queries for the whole client list, not one per client.
        """
        with_future_session = set(
            Session.objects.filter(
                client__active=True,
                session_date__gte=today,
                cancelled=False,
            ).values_list("client_id", flat=True)
        )

        # One query gives us both "recently active" and "has any session"
        last_session_dates = dict(
            Session.objects.filter(client__active=True, cancelled=False)
            .values("client_id")
            .annotate(last_date=Max("session_date"))
            .values_list("client_id", "last_date")
        )
        recently_active = {
            cid
            for cid, d in last_session_dates.items()
            if (today - d).days <= RECENT_ACTIVITY_WINDOW_DAYS
        }
        return with_future_session, recently_active, set(last_session_dates)

    def _strip_inactive_clients(self, totals: dict) -> None:
        """Inactive clients carry no system tags."""
        inactive_with_system = (
            Client.objects.filter(active=False, tags__is_system=True)
            .prefetch_related("tags")
            .distinct()
        )
        for client in inactive_with_system:
            system_tags = [t for t in client.tags.all() if t.is_system]
            if system_tags:
                client.tags.remove(*system_tags)
                totals["removed"] += len(system_tags)
                for t in system_tags:
                    self.stdout.write(
                        self.style.SUCCESS(f"  -{t.slug}: {client.client_code} (inactive)")
                    )

    def _sync_active_clients(
        self, tags, with_future_session, recently_active, has_any_session, totals: dict
    ) -> None:
        """Add or remove each system tag per active client (tags prefetched: no per-client hits)."""
        for client in Client.objects.filter(active=True).prefetch_related("tags"):
            cid = client.id
            client_tag_pks = {t.pk for t in client.tags.all()}

            self._sync_tag(
                client,
                tags["no-next-session"],
                should_have=cid in recently_active and cid not in with_future_session,
                client_tag_pks=client_tag_pks,
                totals=totals,
            )

            has_started = client.first_seen_date is not None or cid in has_any_session
            self._sync_tag(
                client,
                tags["incomplete-intake"],
                should_have=has_started and client.onboarding_complete_date is None,
                client_tag_pks=client_tag_pks,
                totals=totals,
            )

    def _sync_tag(
        self, client, tag, *, should_have: bool, client_tag_pks: set, totals: dict
    ) -> None:
        has_tag = tag.pk in client_tag_pks
        if should_have and not has_tag:
            client.tags.add(tag)
            client_tag_pks.add(tag.pk)
            totals["added"] += 1
            self.stdout.write(self.style.WARNING(f"  +{tag.slug}: {client.client_code}"))
        elif not should_have and has_tag:
            client.tags.remove(tag)
            client_tag_pks.discard(tag.pk)
            totals["removed"] += 1
            self.stdout.write(self.style.SUCCESS(f"  -{tag.slug}: {client.client_code}"))
