# Backup & Restore Scripts

Backing up and restoring the practice data, and the systemd units that do it automatically.

## 📁 Data Directory (IMPORTANT)

Backups and media files live **outside the Git repository** under `MY_PRACTICE_DATA_DIR`.
The path is read from `.env` (default: `../my-practice-data` — sibling directory of the repo clone).

```
$MY_PRACTICE_DATA_DIR/
  backups/    ← PostgreSQL dumps + media archives (bind-mounted → /app/backups in container)
  media/      ← Practice logo, signature, receipt files (bind-mounted → /app/media in container)
```

This ensures a `rm -rf` or `git clean` of the repo never destroys data.

## 📦 Creating a Backup

```bash
./scripts/backup.sh     # in a git checkout (also: ./dev.py backup)
./prod.py backup        # on a prod.py-only installation
```

Both run the same code: `scripts/backup.sh` is a thin wrapper around
`prod.py backup` that points it at the compose file of this checkout. It creates:
- **PostgreSQL dump** (gzip-compressed): `$MY_PRACTICE_DATA_DIR/backups/db_backup_YYYYMMDD_HHMMSS.sql.gz`
- **Media files** (client documents, receipts, logo/signature): `$MY_PRACTICE_DATA_DIR/backups/media_backup_YYYYMMDD_HHMMSS.tar.gz`
- With `BACKUP_PASSPHRASE_FILE` set in `.env`, each archive is encrypted with gpg
  (AES-256) as `….gz.gpg`, after a decrypt round-trip proves it matches the verified original.
  Archives are created mode 0600 either way.

### Features:
- ✅ Timestamped backups (sortable)
- ✅ Compressed (saves storage)
- ✅ Verified before it counts: the dump must end with pg_dump's "dump complete" trailer and the media archive must list every file, otherwise the script exits non-zero and leaves no file behind
- ✅ Automatic cleanup (keeps last 30 days) — runs only after a verified backup, so repeated failures never rotate out the last good one
- ✅ The dashboard warns when the newest backup is older than `BACKUP_MAX_AGE_HOURS` (48 by
  default, production only) — that catches a timer that failed, stopped, or was never installed

`scripts/backup.sh` uses the compose file a plain `docker compose` would here: `COMPOSE_FILE`
from `.env` (set `COMPOSE_FILE=docker-compose.prod.yml` in a checkout that runs the
production stack), else `docker-compose.yml`.

### Example Output:
```
📦 Backing up to /path/to/your/my-practice-data/backups
✅ db_backup_20251215_103000.sql.gz (245 KB)
✅ media_backup_20251215_103000.tar.gz (87 KB)
✨ Backup complete; archives older than 30 days pruned.
```

## 🔄 Restoring from Backup

```bash
# Without arguments it prints usage and where the backups are:
./scripts/restore.sh            # or: ./prod.py restore

# With a specific file:
./scripts/restore.sh $MY_PRACTICE_DATA_DIR/backups/db_backup_20251215_103000.sql.gz
```

Or with media files:
```bash
./scripts/restore.sh \
  $MY_PRACTICE_DATA_DIR/backups/db_backup_20251215_103000.sql.gz \
  $MY_PRACTICE_DATA_DIR/backups/media_backup_20251215_103000.tar.gz
```

### Safety Features:
- ⚠️  Confirmation prompt (prevents accidental overwrites)
- 📊 Shows what will be overwritten
- ✅ Clear success/error messages

## 🤖 Automatic Timers and Auto-Start (systemd)

The unit files live in `scripts/` (source of truth) and are installed as **system** units
in `/etc/systemd/system/` by one script:

```bash
sudo bash scripts/install-system-jobs.sh
```

It fills in the checkout path and your username (the `User=` line, so everything still runs
as you, not as root), enables both timers and the auto-start service, and prints their status.
Re-run it after moving the checkout or pulling changed unit files — it overwrites the
installed copies.

| Unit | Schedule | What it does |
| --- | --- | --- |
| `my-practice-backup.timer` | Daily, random offset within 12 h | Runs `scripts/backup.sh`: PostgreSQL dump + media archive |
| `my-practice-scheduled-jobs.timer` | Hourly, random offset within 5 min | Runs `run_scheduled_jobs`: calendar sync, client tag recalculation, Focus Queue materialize/auto-close, in sequence |
| `my-practice-app.service` | At boot | `dev.py start` once network and Docker are up |

Both timers use `Persistent=true`, so a run missed while the laptop was off or asleep is
caught up at the next start. Each scheduled job is idempotent and a failure in one is
logged without blocking the others (`my_practice/management/commands/run_scheduled_jobs.py`);
any of them can still be run on its own, e.g. `./dev.py manage update_client_tags`.

Why system units rather than user units under `~/.config/systemd/user/`: the app has to
start at boot without anyone logging in, and the unit files set `User=`/`Group=`, which a
user unit cannot use — copied there unedited, they fail to start.

### Moving from user units

Earlier versions of this page installed the timers as user units (and before that as three
separate timers: `update-client-tags`, `fetch-calendar-events`, `sync-focus-queue`). Remove
them before running the installer, or every backup and job runs twice:

```bash
systemctl --user disable --now 'my-practice-*.timer'
rm -f ~/.config/systemd/user/my-practice-*.{timer,service}
systemctl --user daemon-reload
```

The installer warns if it finds any left over.

### Check status

```bash
systemctl list-timers 'my-practice-*'
journalctl -u my-practice-backup.service -n 50
journalctl -u my-practice-scheduled-jobs.service -n 50
systemctl status my-practice-app.service --no-pager
```

The dashboard also warns when the newest backup is older than `BACKUP_MAX_AGE_HOURS`, which
catches a timer that stopped or was never installed.

### Stop, disable, re-enable

Enable or disable the **timers**, never the oneshot `.service` units they trigger.

```bash
sudo systemctl disable --now my-practice-backup.timer   # stop automatic backups
sudo systemctl enable --now my-practice-backup.timer    # turn them back on
sudo systemctl disable my-practice-app.service          # no auto-start at boot
sudo systemctl start my-practice-app.service            # start the app now
```

### Troubleshooting

- **Backups not running:** check `systemctl is-active my-practice-backup.timer`, then the
  journal above. Run `./scripts/backup.sh` by hand — it exits non-zero (and the unit shows
  as failed) whenever the dump or media archive fails verification, and a `❌` line names the
  step. Check Docker is up: `docker ps`.
- **`status=203/EXEC` or `Permission denied`** (SELinux, or a checkout on a filesystem
  mounted `noexec`): the units already call their scripts through an interpreter
  (`/usr/bin/env bash …`, `/usr/bin/env python3 …`). If you edited them, keep it that way, then
  `sudo systemctl daemon-reload`.
- **Immutable hosts (Bluefin, Silverblue):** `/etc/systemd/system/` is writable and
  survives `rpm-ostree` updates, so the installer works unchanged.

## 📤 External Backups

The system creates backups in `$MY_PRACTICE_DATA_DIR/backups/` (outside the repository).
From there they are manually copied to external media (external disk, NAS).

**Note**: For data protection reasons, backups containing client data are not uploaded to
external cloud services.

## 📋 Checklist

- [x] Make `backup.sh` and `restore.sh` executable: `chmod +x scripts/*.sh`
- [x] Create first test backup: `./scripts/backup.sh`
- [x] Perform test restore (on test data!)
- [x] Set up automatic backups via systemd
- [x] External backup configured (manual sync to external disk/NAS)
- [ ] Calendar reminder: perform restore test monthly

## 🚨 Disaster Recovery

In an emergency (e.g. data loss):

1. **Stop containers**: `docker compose down`
2. **Fresh start**: `docker compose up -d`
3. **Restore latest backup**: `./scripts/restore.sh $MY_PRACTICE_DATA_DIR/backups/db_backup_LATEST.sql.gz $MY_PRACTICE_DATA_DIR/backups/media_backup_LATEST.tar.gz`
4. **Restart Django**: `docker compose restart django`
5. **Verify**: `./dev.py manage encryption check` confirms `FERNET_KEY` opens the restored data, then open http://localhost:8000 and check it

## 💡 Tips

- **Before major changes**: Always run `./scripts/backup.sh` manually
- **Before Django migrations**: Create a backup
- **Test regularly**: Perform a restore on a test system monthly
- **Monitoring**: `journalctl -u my-practice-backup.service` for the timer's runs; the dashboard warns when the newest backup is too old
- **Retention**: 30 days, `BACKUP_RETENTION_DAYS` in `prod.py`
