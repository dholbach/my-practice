"""
How old the newest backup is, for the dashboard warning.

The backup timer runs outside the app, and every way it can stop — a failed
run, a timer that was never installed, a full disk, a renamed unit — is
silent. Checking the result instead of the mechanism catches all of them:
the dashboard warns when the newest verified database backup in BACKUP_DIR
(bind-mounted from MY_PRACTICE_DATA_DIR/backups) is missing or too old.
"""

from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

# Written only after verification (see prod.py run_backup), so their presence
# means a good backup; temp files start with a dot and never match.
BACKUP_GLOBS = ("db_backup_*.sql.gz", "db_backup_*.sql.gz.gpg")


def latest_backup_time(backup_dir: str | Path) -> datetime | None:
    """Modification time of the newest database backup, or None if there is none."""
    directory = Path(backup_dir)
    if not directory.is_dir():
        return None
    times = [path.stat().st_mtime for pattern in BACKUP_GLOBS for path in directory.glob(pattern)]
    if not times:
        return None
    return datetime.fromtimestamp(max(times), tz=timezone.get_current_timezone())


def stale_backup_warning(now: datetime | None = None) -> dict | None:
    """Context for the dashboard warning, or None when backups are current or the check is off."""
    max_age_hours = settings.BACKUP_MAX_AGE_HOURS
    if not max_age_hours:
        return None
    latest = latest_backup_time(settings.BACKUP_DIR)
    if latest is None:
        return {"latest": None}
    age = (now or timezone.now()) - latest
    if age <= timedelta(hours=max_age_hours):
        return None
    return {"latest": latest, "days": age.days}
