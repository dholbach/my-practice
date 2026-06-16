# P-027: Fahrtkosten-Berechnung (Entfernungspauschale)

**Status**: DONE (2026-03-27)

---

## Ziel

Automatische Berechnung der steuerlich absetzbaren Fahrtkosten (Entfernungspauschale) für die
Steuerjahresübersicht. Der Therapeut fährt an bestimmten Wochentagen in die Praxis — das System
soll die Anzahl der Praxistage pro Jahr aus diesen Wochentagen ableiten, Feiertage (Berlin)
abziehen, und den absetzbaren Betrag nach § 9 Abs. 1 Nr. 4 EStG ausrechnen.

**Ergebnis**: Auf der Seite `/reports/steuerjahr/` erscheint ein neuer Abschnitt
"Fahrtkosten (Entfernungspauschale)" mit Praxistage-Zählung und berechnetem Betrag.

---

## Steuerlicher Hintergrund

**Entfernungspauschale (§ 9 Abs. 1 Nr. 4 EStG)**:
- 0,30 € / km (erste 20 km, einfache Strecke) × Praxistage
- 0,38 € / km (ab km 21, einfache Strecke) × Praxistage

Beispiel: 25 km Entfernung, 180 Praxistage/Jahr:
```
20 km × 0,30 € × 180 = 1.080,00 €
 5 km × 0,38 € × 180 =   342,00 €
Gesamt:               = 1.422,00 €
```

Nur Selbstständige mit regelmäßiger erster Tätigkeitsstätte (Praxis) können die
Entfernungspauschale ansetzen. Bei Heimarbeitstagen zählt der Tag **nicht**.

---

## Geplante Änderungen

### 1. `Practice`-Modell (neue Felder)

```python
# Fahrtkosten-Konfiguration
commute_distance_km = models.PositiveIntegerField(
    null=True, blank=True,
    verbose_name="Entfernung zur Praxis (km)",
    help_text="Einfache Strecke in km (z.B. 12). Wird für Entfernungspauschale verwendet.",
)
practice_weekdays = models.JSONField(
    default=list, blank=True,
    verbose_name="Praxistage (Wochentage)",
    help_text="Liste der Wochentage, an denen die Praxis besucht wird (0=Mo, 1=Di, …, 4=Fr).",
)
```

Migration: `0059_practice_fahrtkosten`

### 2. `utils/practice_days.py` — `PracticeDayCalculator`

```python
class PracticeDayCalculator:
    """Berechnet Praxistage und Entfernungspauschale für ein Steuerjahr."""

    RATE_FIRST_20_KM = Decimal("0.30")
    RATE_ABOVE_20_KM = Decimal("0.38")

    def __init__(self, practice: Practice, year: int):
        self.practice = practice
        self.year = year

    def count_practice_days(self) -> int:
        """Zählt Werktage des Jahres auf den konfigurierten Wochentagen (ohne Feiertage Berlin)."""
        ...

    def compute_deduction(self) -> Decimal:
        """Berechnet Entfernungspauschale: Tage × Pauschalbetrag(km)."""
        ...

    def berlin_holidays(self) -> set[date]:
        """Gibt die gesetzlichen Berliner Feiertage für self.year zurück."""
        ...
```

**Feiertage Berlin** (hardcoded, keine externe Abhängigkeit):
- Neujahr (01.01.), Heilige Drei Könige (06.01. — Berlin: ❌), Karfreitag, Ostermontag,
  1. Mai, Christi Himmelfahrt, Pfingstmontag, Tag der Deutschen Einheit (03.10.),
  Reformationstag (31.10. — Berlin: ✅ seit 2019), 1. Weihnachtstag, 2. Weihnachtstag
- Bewegliche Feiertage via `easter()` (Python `dateutil` oder eigene Oster-Formel)

### 3. `tax_views.py` — `tax_year_summary` erweitern

```python
from ..utils.practice_days import PracticeDayCalculator

calc = PracticeDayCalculator(practice, year)
context["fahrtkosten_days"] = calc.count_practice_days()
context["fahrtkosten_deduction"] = calc.compute_deduction()
context["fahrtkosten_distance"] = practice.commute_distance_km
context["practice_weekdays"] = practice.practice_weekdays
```

### 4. `tax_year_summary.html` — neuer Abschnitt

Unterhalb der Ausgabentabelle: aufklappbarer `<details>`-Block mit:
- Konfigurierte Wochentage (Mo–Fr Chips)
- Entfernung (km)
- Berechnete Praxistage
- Berechneter Betrag (aufgeteilt: erste 20 km / ab km 21)
- Hinweis: "Als Betriebsausgabe eintragen oder als Anlage N (wenn Arbeitnehmer)" — entfällt
  hier, da Selbstständiger → direkte Betriebsausgabe

### 5. Admin / `practice_views.py`

Felder `commute_distance_km` + `practice_weekdays` in den Praxiseinstellungen
(Admin + ggf. Praxis-Einstellungs-View).

---

## Datenbindung

- **Wochentage**: `[0, 1, 2, 4]` = Mo, Di, Mi, Fr (Python `weekday()` Konvention)
- **Kein Feiertags-Package**: Berliner Feiertage hartkodiert; Oster-Berechnung via
  Gaußsche Formel oder `datetime`-Arithmetik — keine neue Abhängigkeit
- **Heimarbeitstage**: vorerst nicht erfasst; als TODO vermerken

---

## Scope-Grenze (Out of scope)

- Heimarbeitstage abziehen (erfordert separates Feld / Kalenderintegration)
- Andere Bundesländer als Berlin (parametrisierbar via Practice.state — zukünftig)
- Fahrten zu Supervision / Fortbildungen (separate Kategorie, eigene Rechnung)
- Automatisches Eintragen als `CompanyExpense` (Benutzer trägt manuell ein, System liefert Betrag)

---

## Akzeptanzkriterien

- [ ] Neue `Practice`-Felder in Admin konfigurier- und speicherbar
- [ ] `PracticeDayCalculator.count_practice_days()` liefert plausible Werte (Mo–Fr ohne Feiertage ≈ 250/Jahr)
- [ ] Entfernungspauschale wird korrekt auf `/reports/steuerjahr/` angezeigt
- [ ] Bei nicht konfigurierter Entfernung: Abschnitt ausgeblendet (nicht 0 €)
- [ ] Tests: `test_practice_days.py` mit Grenzfällen (Schaltjahr, Jahreswechsel, kein Praxistag)

---

## Technische Notizen

- `practice_weekdays` als `JSONField(default=list)` statt `ArrayField` → portabler, kein
  PostgreSQL-spezifisches Feld nötig; Validierung im Admin/Form
- Bestehende Migration-Reihenfolge: nach `0058_client_document`
- `PracticeDayCalculator` in `utils/__init__.py` exportieren
