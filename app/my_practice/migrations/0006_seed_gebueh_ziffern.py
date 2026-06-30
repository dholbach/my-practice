"""Seed GebüH Ziffern catalogue (GebüH 1985, rates confirmed by practitioner)."""

from decimal import Decimal

from django.db import migrations


ZIFFERN = [
    # Anamnese / Erstgespräch
    {
        "nummer": "1",
        "bezeichnung": "Anamnese / Folgeanamnese",
        "satz_max": Decimal("41.00"),
        "satz_min": Decimal("15.40"),
        "anmerkung": (
            "Erstanamnese nur 1× jährlich abrechenbar. "
            "Folgeanamnese max. 3× innerhalb von 6 Monaten."
        ),
        "max_haeufigkeit": 3,
        "bezugszeitraum_tage": 180,
        "sort_order": 10,
    },
    {
        "nummer": "19.5",
        "bezeichnung": "Psychologische Exploration mit eingehender Beratung",
        "satz_max": Decimal("46.00"),
        "satz_min": Decimal("15.50"),
        "anmerkung": "",
        "max_haeufigkeit": None,
        "bezugszeitraum_tage": None,
        "sort_order": 20,
    },
    # Laufende Behandlung
    {
        "nummer": "19.1",
        "bezeichnung": "Psychotherapie bis 30 Min",
        "satz_max": Decimal("26.00"),
        "satz_min": Decimal("15.50"),
        "anmerkung": "",
        "max_haeufigkeit": None,
        "bezugszeitraum_tage": None,
        "sort_order": 30,
    },
    {
        "nummer": "19.2",
        "bezeichnung": "Psychotherapie 50–90 Min",
        "satz_max": Decimal("46.00"),
        "satz_min": Decimal("26.00"),
        "anmerkung": "Übliche Ziffer für eine reguläre Sitzung.",
        "max_haeufigkeit": None,
        "bezugszeitraum_tage": None,
        "sort_order": 40,
    },
    {
        "nummer": "19.8",
        "bezeichnung": "Behandlung durch Hypnose (Einzelperson)",
        "satz_max": Decimal("26.00"),
        "satz_min": Decimal("15.50"),
        "anmerkung": "",
        "max_haeufigkeit": None,
        "bezugszeitraum_tage": None,
        "sort_order": 50,
    },
    # Diagnostik / Sonstiges
    {
        "nummer": "19.3",
        "bezeichnung": "Ausstellung eines psychodiagnostischen Befundes",
        "satz_max": Decimal("38.50"),
        "satz_min": Decimal("15.50"),
        "anmerkung": "",
        "max_haeufigkeit": None,
        "bezugszeitraum_tage": None,
        "sort_order": 60,
    },
    {
        "nummer": "19.6",
        "bezeichnung": "Anwendung / Auswertung von Testverfahren (z.B. TAT, Rorschach)",
        "satz_max": Decimal("38.50"),
        "satz_min": Decimal("15.50"),
        "anmerkung": "",
        "max_haeufigkeit": None,
        "bezugszeitraum_tage": None,
        "sort_order": 70,
    },
    {
        "nummer": "19.4",
        "bezeichnung": "Psychotherapeutisches Gutachten (je Seite)",
        "satz_max": Decimal("15.50"),
        "satz_min": Decimal("15.50"),
        "anmerkung": "Abrechnung je angefangene Seite.",
        "max_haeufigkeit": None,
        "bezugszeitraum_tage": None,
        "sort_order": 80,
    },
    {
        "nummer": "4",
        "bezeichnung": "Eingehende Beratung (mindestens 15 Min)",
        "satz_max": Decimal("22.00"),
        "satz_min": Decimal("16.40"),
        "anmerkung": (
            "Nur als Alleinleistung pro Sitzung erstattungsfähig — "
            "nicht mit anderen Ziffern derselben Sitzung kombinierbar."
        ),
        "max_haeufigkeit": None,
        "bezugszeitraum_tage": None,
        "sort_order": 90,
    },
]


def seed_ziffern(apps, schema_editor):
    GebuhZiffer = apps.get_model("my_practice", "GebuhZiffer")
    for data in ZIFFERN:
        GebuhZiffer.objects.get_or_create(nummer=data["nummer"], defaults=data)


def unseed_ziffern(apps, schema_editor):
    GebuhZiffer = apps.get_model("my_practice", "GebuhZiffer")
    GebuhZiffer.objects.filter(nummer__in=[d["nummer"] for d in ZIFFERN]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("my_practice", "0005_gebueh_models"),
    ]

    operations = [
        migrations.RunPython(seed_ziffern, reverse_code=unseed_ziffern),
    ]
