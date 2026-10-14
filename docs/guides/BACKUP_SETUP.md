# Backup Setup

> **Back up `FERNET_KEY` separately.** Clinical records, client/inquiry notes and
> client documents are stored encrypted in both the database dump and the media
> archive. A restored backup is unreadable without the key it was written with — keep
> it in a password manager, not on the same card. After a restore, `manage.py
> encryption check` confirms the key opens everything. See
> [CLINICAL_DATA_SECURITY.md](CLINICAL_DATA_SECURITY.md).

## MicroSD Offsite Backup

### Hardware

Two inexpensive UHS-I MicroSD cards are entirely sufficient — e.g. **SanDisk Ultra** or
**Samsung EVO Plus**, 32–64 GB, together about €15.

UHS-II/III and V30 are designed for high-speed cameras. With ~1 GB of backup every two
weeks, the difference amounts to a few seconds — completely irrelevant.

### Rotation

The cards are written to alternately (Card A → Card B → Card A → …):

1. Take the other card from the locked cabinet
2. Copy the latest Pika backup snapshot
3. Encrypt the card (same passphrase as USB/NAS)
4. Quick test: check 1–2 files + database record count
5. Label: "Card A/B — [date]"
6. Return to the locked cabinet

**No disposal schedule.** At this usage level, the cards are still virtually new after years.
Check readability every few years — that's sufficient.

The in-app checklist (`/backups/checklist/quarterly/`) walks through the process.

---

## Without a git checkout (`prod.py` only)

A self-hosted installation set up with `./prod.py setup` has no `scripts/` directory.
Back up with:

```bash
./prod.py backup                        # database + media → $MY_PRACTICE_DATA_DIR/backups
./prod.py restore <db_backup> [media]   # overwrites the current data; asks first
```

Schedule it daily — for example with cron (`crontab -e`):

```
17 3 * * * cd /path/to/my-practice && ./prod.py backup >> backup.log 2>&1
```

Set `BACKUP_PASSPHRASE_FILE` in `.env` to encrypt the archives with gpg (see
`.env.example`). The dashboard shows a warning when the newest backup is more than
48 hours old (`BACKUP_MAX_AGE_HOURS`), so a schedule that silently stopped does not go
unnoticed. Copying the backup directory off the machine (USB, NAS) is still up to you.

## In a git checkout: automatic backups with systemd

```bash
sudo bash scripts/install-system-jobs.sh
```

installs a daily backup timer, the hourly scheduled-jobs timer and the app's auto-start
service. What each unit does, how to check on them, moving over from the older user-unit
setup and troubleshooting: [SCRIPTS.md § Automatic Timers and Auto-Start](../operations/SCRIPTS.md#-automatic-timers-and-auto-start-systemd).
