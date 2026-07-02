"""
Fahrtkosten / Entfernungspauschale calculation (P-027).

§9 Abs. 1 Nr. 4 EStG: the daily commute deduction for each day actually driven
to the practice. Rates (as of 2024):
  - 0.30 €/km for the first 20 km (one-way)
  - 0.38 €/km for every km beyond 20 km

The deduction basis is the number of *actual session days* in the tax year —
i.e. days where at least one session is recorded in the database — filtered to
the practitioner's configured weekdays. The calendar-based estimate
(weekdays − public holidays − TimeOff) is also computed for reference but is
not used for the deduction itself.

Public holidays ARE still needed: they are excluded from the calendar-based
``practice_days`` count (which serves as a reference / upper bound).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Practice


# Entfernungspauschale rates (§9 Abs. 1 Nr. 4 EStG)
RATE_FIRST_20_KM = Decimal("0.30")
RATE_ABOVE_20_KM = Decimal("0.38")
KM_THRESHOLD = 20

# Home-Office-Pauschale (§4 Abs. 5 Nr. 6b EStG; annual cap in days)
HOME_OFFICE_DAILY_RATE = Decimal("6.00")
HOME_OFFICE_MAX_DAYS = 210


def _easter(year: int) -> date:
    """Compute Easter Sunday via the Anonymous Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    month = (h + ll - 7 * m + 114) // 31
    day = ((h + ll - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def berlin_public_holidays(year: int) -> set[date]:
    """
    Return the set of Berlin public holidays for the given year.

    Includes all federal holidays observed in Berlin plus Berlin-specific ones
    (Tag der Deutschen Einheit, Reformationstag since 2018, International Women's Day since 2019).
    Does NOT include Heilige Drei Könige (Berlin: not a public holiday).
    """
    easter = _easter(year)

    holidays = {
        date(year, 1, 1),  # Neujahr
        easter - timedelta(days=2),  # Karfreitag
        easter,  # Ostersonntag (kein gesetzl. Feiertag, but included for safety)
        easter + timedelta(days=1),  # Ostermontag
        date(year, 5, 1),  # Tag der Arbeit
        easter + timedelta(days=39),  # Christi Himmelfahrt
        easter + timedelta(days=49),  # Pfingstsonntag
        easter + timedelta(days=50),  # Pfingstmontag
        date(year, 10, 3),  # Tag der Deutschen Einheit
        date(year, 12, 25),  # 1. Weihnachtstag
        date(year, 12, 26),  # 2. Weihnachtstag
    }

    # Reformationstag: Berlin since 2018
    if year >= 2018:
        holidays.add(date(year, 10, 31))

    # Internationaler Frauentag: Berlin since 2019
    if year >= 2019:
        holidays.add(date(year, 3, 8))

    return holidays


def _timeoff_dates_for_year(year: int) -> set[date]:
    """Return all dates within TimeOff entries that fall inside the given year."""
    from ..models import TimeOff

    entries = TimeOff.objects.filter(
        start_date__year__lte=year,
        end_date__year__gte=year,
    )
    off_dates: set[date] = set()
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    for entry in entries:
        current = max(entry.start_date, year_start)
        end = min(entry.end_date, year_end)
        while current <= end:
            off_dates.add(current)
            current += timedelta(days=1)
    return off_dates


@dataclass
class FahrtkostenResult:
    """Result of a Fahrtkosten calculation."""

    year: int
    distance_km: int
    practice_days: int  # calendar-based (weekdays - holidays - timeoff)
    session_days: int  # actual days with at least one session in the DB
    deduction_total: Decimal
    deduction_first_20_km: Decimal
    deduction_above_20_km: Decimal
    configured_weekdays: list[int]  # 0=Mo … 4=Fr
    total_possible_days: int  # weekdays in year matching practice_weekdays
    timeoff_days_excluded: int  # days excluded due to TimeOff entries

    @property
    def is_configured(self) -> bool:
        return self.distance_km > 0 and bool(self.configured_weekdays)


@dataclass
class HomeOfficeResult:
    """Result of a home-office day calculation."""

    year: int
    configured_practice_weekdays: list[int]  # 0=Mo … 4=Fr
    home_office_weekdays: list[int]  # 0=Mo … 4=Fr
    total_possible_days: int
    timeoff_days_excluded: int
    home_office_days: int  # calendar-based (weekdays - holidays - timeoff)
    capped_days: int  # legal cap for the pauschale
    deduction_total: Decimal

    @property
    def is_configured(self) -> bool:
        return bool(self.configured_practice_weekdays)


class PracticeDayCalculator:
    """
    Calculate practice days and Entfernungspauschale for a tax year.

    Practice days = all days in the year on the configured weekdays,
    minus public holidays (Berlin), minus TimeOff periods recorded in the system.

    Args:
        practice: Practice model instance with commute_distance_km and practice_weekdays
        year: The tax year to calculate for
    """

    def __init__(self, practice: Practice, year: int) -> None:
        self.practice = practice
        self.year = year

    def _session_dates(self) -> set[date]:
        """Return all dates in this year that have at least one session (any client)."""
        from ..models import Session

        return set(
            Session.objects.filter(session_date__year=self.year).values_list(
                "session_date", flat=True
            )
        )

    def calculate(self) -> FahrtkostenResult:
        """
        Calculate practice days and Entfernungspauschale.

        Returns a FahrtkostenResult dataclass. If practice is not configured
        (no distance or no weekdays), returns a result with zeros.
        """
        distance_km: int = self.practice.commute_distance_km or 0
        weekdays: list[int] = list(self.practice.practice_weekdays or [])

        if not distance_km or not weekdays:
            return FahrtkostenResult(
                year=self.year,
                distance_km=distance_km,
                practice_days=0,
                session_days=0,
                deduction_total=Decimal("0"),
                deduction_first_20_km=Decimal("0"),
                deduction_above_20_km=Decimal("0"),
                configured_weekdays=weekdays,
                total_possible_days=0,
                timeoff_days_excluded=0,
            )

        holidays = berlin_public_holidays(self.year)
        timeoff = _timeoff_dates_for_year(self.year)
        sessions = self._session_dates()

        year_start = date(self.year, 1, 1)
        year_end = date(self.year, 12, 31)

        total_possible = 0
        timeoff_excluded = 0
        practice_days = 0

        current = year_start
        while current <= year_end:
            if current.weekday() in weekdays:
                total_possible += 1
                if current in holidays:
                    pass  # holiday, not a practice day
                elif current in timeoff:
                    timeoff_excluded += 1
                else:
                    practice_days += 1
            current += timedelta(days=1)

        # Session-based count: distinct days with at least one session,
        # restricted to the configured weekdays. Public holidays are NOT
        # excluded here — if a session actually happened, the drive is claimable.
        session_days = len({d for d in sessions if d.weekday() in weekdays})

        # Deduction basis: actual session days (§9: days you drove to the practice)
        km = distance_km
        first_part_km = min(km, KM_THRESHOLD)
        above_part_km = max(km - KM_THRESHOLD, 0)

        deduction_first = Decimal(str(first_part_km)) * RATE_FIRST_20_KM * session_days
        deduction_above = Decimal(str(above_part_km)) * RATE_ABOVE_20_KM * session_days

        return FahrtkostenResult(
            year=self.year,
            distance_km=km,
            practice_days=practice_days,
            session_days=session_days,
            deduction_total=deduction_first + deduction_above,
            deduction_first_20_km=deduction_first,
            deduction_above_20_km=deduction_above,
            configured_weekdays=weekdays,
            total_possible_days=total_possible,
            timeoff_days_excluded=timeoff_excluded,
        )


class HomeOfficeDayCalculator:
    """Calculate home-office days and Home-Office-Pauschale for a tax year."""

    def __init__(self, practice: Practice, year: int) -> None:
        self.practice = practice
        self.year = year

    def calculate(self) -> HomeOfficeResult:
        """Calculate home-office weekdays and deductible pauschale."""
        practice_weekdays = sorted(
            {int(d) for d in (self.practice.practice_weekdays or []) if 0 <= int(d) <= 4}
        )
        home_office_weekdays = [d for d in range(5) if d not in practice_weekdays]

        if not practice_weekdays:
            return HomeOfficeResult(
                year=self.year,
                configured_practice_weekdays=[],
                home_office_weekdays=[],
                total_possible_days=0,
                timeoff_days_excluded=0,
                home_office_days=0,
                capped_days=0,
                deduction_total=Decimal("0"),
            )

        holidays = berlin_public_holidays(self.year)
        timeoff = _timeoff_dates_for_year(self.year)

        total_possible = 0
        timeoff_excluded = 0
        home_office_days = 0

        current = date(self.year, 1, 1)
        year_end = date(self.year, 12, 31)
        while current <= year_end:
            if current.weekday() in home_office_weekdays:
                total_possible += 1
                if current in holidays:
                    pass
                elif current in timeoff:
                    timeoff_excluded += 1
                else:
                    home_office_days += 1
            current += timedelta(days=1)

        capped_days = min(home_office_days, HOME_OFFICE_MAX_DAYS)
        deduction_total = Decimal(str(capped_days)) * HOME_OFFICE_DAILY_RATE

        return HomeOfficeResult(
            year=self.year,
            configured_practice_weekdays=practice_weekdays,
            home_office_weekdays=home_office_weekdays,
            total_possible_days=total_possible,
            timeoff_days_excluded=timeoff_excluded,
            home_office_days=home_office_days,
            capped_days=capped_days,
            deduction_total=deduction_total,
        )


@dataclass
class DayAuditEntry:
    """A single row in the workday audit list."""

    day: date
    day_type: str  # "practice" | "home_office" | "holiday" | "timeoff" | "weekend"
    sessions: int  # number of sessions on this day (0 if none / non-session day)
    holiday_name: str  # non-empty only for public holidays


@dataclass
class WorkdayAuditResult:
    """Full year workday audit data."""

    year: int
    entries: list[DayAuditEntry]
    practice_days: int
    home_office_days: int
    holiday_count: int
    timeoff_days: int


# Human-readable Berlin holiday names for the audit list
def _berlin_holiday_names(year: int) -> dict[date, str]:
    """Return a mapping of Berlin public holiday dates to German names."""
    easter = _easter(year)
    names: dict[date, str] = {
        date(year, 1, 1): "Neujahr",
        easter - timedelta(days=2): "Karfreitag",
        easter: "Ostersonntag",
        easter + timedelta(days=1): "Ostermontag",
        date(year, 5, 1): "Tag der Arbeit",
        easter + timedelta(days=39): "Christi Himmelfahrt",
        easter + timedelta(days=49): "Pfingstsonntag",
        easter + timedelta(days=50): "Pfingstmontag",
        date(year, 10, 3): "Tag der Deutschen Einheit",
        date(year, 12, 25): "1. Weihnachtstag",
        date(year, 12, 26): "2. Weihnachtstag",
    }
    if year >= 2018:
        names[date(year, 10, 31)] = "Reformationstag"
    if year >= 2019:
        names[date(year, 3, 8)] = "Internationaler Frauentag"
    return names


class WorkdayAuditCalculator:
    """
    Build a full-year day-by-day audit list showing each weekday's classification.

    Only weekdays (Mon–Fri) are included; Sat/Sun are skipped.
    Day types:
      - "practice"     — a configured practice weekday, not holiday/timeoff
      - "home_office"  — a non-practice weekday, not holiday/timeoff
      - "holiday"      — a Berlin public holiday (any weekday)
      - "timeoff"      — within a TimeOff period (practice or HO day, not holiday)
    """

    def __init__(self, practice: "Practice", year: int) -> None:
        self.practice = practice
        self.year = year

    def _session_counts(self) -> dict[date, int]:
        """Return {date: session_count} for all non-cancelled sessions in the year."""
        from ..models import Session

        qs = Session.objects.filter(
            client__practice=self.practice,
            session_date__year=self.year,
            cancelled=False,
        ).values_list("session_date", flat=True)
        counts: dict[date, int] = {}
        for d in qs:
            counts[d] = counts.get(d, 0) + 1
        return counts

    def calculate(self) -> WorkdayAuditResult:
        """Build the audit list for the full year."""
        practice_weekdays = set(
            int(d) for d in (self.practice.practice_weekdays or []) if 0 <= int(d) <= 4
        )
        holidays = berlin_public_holidays(self.year)
        holiday_names = _berlin_holiday_names(self.year)
        timeoff = _timeoff_dates_for_year(self.year)
        session_counts = self._session_counts()

        entries: list[DayAuditEntry] = []
        practice_days = home_office_days = holiday_count = timeoff_days = 0

        current = date(self.year, 1, 1)
        year_end = date(self.year, 12, 31)
        while current <= year_end:
            wd = current.weekday()
            if wd >= 5:  # skip weekends
                current += timedelta(days=1)
                continue

            sessions = session_counts.get(current, 0)

            if current in holidays:
                day_type = "holiday"
                holiday_count += 1
            elif current in timeoff:
                day_type = "timeoff"
                timeoff_days += 1
            elif wd in practice_weekdays:
                day_type = "practice"
                practice_days += 1
            else:
                day_type = "home_office"
                home_office_days += 1

            entries.append(
                DayAuditEntry(
                    day=current,
                    day_type=day_type,
                    sessions=sessions,
                    holiday_name=holiday_names.get(current, ""),
                )
            )
            current += timedelta(days=1)

        return WorkdayAuditResult(
            year=self.year,
            entries=entries,
            practice_days=practice_days,
            home_office_days=home_office_days,
            holiday_count=holiday_count,
            timeoff_days=timeoff_days,
        )
