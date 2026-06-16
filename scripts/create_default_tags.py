#!/usr/bin/env python
"""
Create common client tags for therapy practice organization.
Run this once to set up a standard set of tags.

Usage: ./dev.py run scripts/create_default_tags.py
"""

import os
import sys

import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from my_practice.models import ClientTag  # noqa: E402

# Define common tags for therapy practice
DEFAULT_TAGS = [
    # Process-related tags
    {
        "name": "missing-paperwork",
        "color": "red",
        "description": "Intake oder andere erforderliche Dokumente fehlen noch",
    },
    {
        "name": "follow-up",
        "color": "orange",
        "description": "Benötigt Follow-up Kontakt oder Check-in",
    },
    {
        "name": "needs-documentation",
        "color": "yellow",
        "description": "Sitzungsnotizen oder diagnostische Materialien ausstehend",
    },
    {
        "name": "probationary",
        "color": "blue",
        "description": "In Probephase (erste 5-10 Sitzungen)",
    },
    # Status tags for inactive clients
    {
        "name": "end-process",
        "color": "green",
        "description": "Therapie erfolgreich abgeschlossen",
    },
    {
        "name": "no-fit",
        "color": "gray",
        "description": "Klient hat entschieden, dass Therapie nicht passt",
    },
    {
        "name": "moved-away",
        "color": "gray",
        "description": "Klient ist umgezogen / nicht mehr erreichbar",
    },
    {
        "name": "referral-out",
        "color": "purple",
        "description": "An anderen Therapeuten / andere Einrichtung überwiesen",
    },
    # Priority tags
    {
        "name": "urgent",
        "color": "red",
        "description": "Dringende Aufmerksamkeit erforderlich",
    },
    {
        "name": "priority-client",
        "color": "pink",
        "description": "Prioritätsklient (z.B. komplexer Fall, besondere Betreuung)",
    },
]


def create_default_tags():
    """Create default tags if they don't exist"""
    created_count = 0
    skipped_count = 0

    print("Creating default client tags...\n")

    for tag_data in DEFAULT_TAGS:
        slug = tag_data["name"]
        tag, created = ClientTag.objects.get_or_create(
            slug=slug,
            defaults=tag_data,
        )

        if created:
            print(f"✓ Created: {tag.name} ({tag.get_color_display()})")
            created_count += 1
        else:
            print(f"⊙ Exists:  {tag.name} ({tag.get_color_display()})")
            skipped_count += 1

    print(f"\n{'=' * 50}")
    print(f"Summary: {created_count} created, {skipped_count} already existed")
    print(f"{'=' * 50}\n")

    # Note about automatic tag
    print("Note: The 'no-next-session' tag is created automatically")
    print("Run: ./dev.py manage update_client_tags")


if __name__ == "__main__":
    create_default_tags()
