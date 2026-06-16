# Backup & Restore Scripts

These scripts provide easy backup and restoration of the payments system data.

## 📁 Data Directory (IMPORTANT)

Backups and media files live **outside the Git repository** under `PAYMENTS_DATA_DIR`.
The path is read from `.env` (default: `../payments-data` — sibling directory of the repo clone).

```
$PAYMENTS_DATA_DIR/
  backups/    ← PostgreSQL dumps + media archives (bind-mounted → /app/backups in container)
  media/      ← Practice logo, signature, receipt files (bind-mounted → /app/media in container)
```

This ensures a `rm -rf` or `git clean` of the repo never destroys data.

## 📦 Creating a Backup

```bash
./scripts/backup.sh
```

The script creates (CWD-independent — uses `$SCRIPT_DIR` for path resolution):
- **PostgreSQL dump** (gzip-compressed): `$PAYMENTS_DATA_DIR/backups/db_backup_YYYYMMDD_HHMMSS.sql.gz`
- **Media files** (logo/signature): `$PAYMENTS_DATA_DIR/backups/media_backup_YYYYMMDD_HHMMSS.tar.gz`

### Features:
- ✅ Timestamped backups (sortable)
- ✅ Compressed (saves storage)
- ✅ Automatic cleanup (keeps last 30 days)
- ✅ Coloured output with size information

### Example Output:
```
📦 Starting backup at Sun Dec 15 10:30:00 CET 2025
   Data directory: /path/to/your/my-practice-data
🗄️  Backing up PostgreSQL database...
✅ Database backup complete: /path/to/your/my-practice-data/backups/db_backup_20251215_103000.sql.gz (245K)
📁 Backing up media files...
✅ Media backup complete: /path/to/your/my-practice-data/backups/media_backup_20251215_103000.tar.gz (87K)
🧹 Cleaning up old backups (keeping last 30 days)...
✨ Backup completed successfully
```

## 🔄 Restoring from Backup

```bash
# restore.sh shows available backups automatically when called without arguments:
./scripts/restore.sh

# With a specific file:
./scripts/restore.sh $PAYMENTS_DATA_DIR/backups/db_backup_20251215_103000.sql.gz
```

Or with media files:
```bash
./scripts/restore.sh \
  $PAYMENTS_DATA_DIR/backups/db_backup_20251215_103000.sql.gz \
  $PAYMENTS_DATA_DIR/backups/media_backup_20251215_103000.tar.gz
```

### Safety Features:
- ⚠️  Confirmation prompt (prevents accidental overwrites)
- 📊 Shows what will be overwritten
- ✅ Clear success/error messages

## 🤖 Automatic Timers (Systemd user units)

Three timers run as user systemd units (no sudo needed). The unit files live in
`scripts/` (source of truth) and are installed to `~/.config/systemd/user/`.

| Timer | Schedule | What it does |
| --- | --- | --- |
| `my-practice-backup` | Daily (random offset) | PostgreSQL dump + media archive |
| `my-practice-update-client-tags` | Hourly (random offset) | Recalculate tag rules for all clients |
| `my-practice-fetch-calendar-events` | Hourly (random offset) | Pull Google Calendar events into pending queue |

### Install / reinstall after path changes

```bash
DEST=~/.config/systemd/user
cp scripts/my-practice-backup.service          $DEST/
cp scripts/my-practice-backup.timer            $DEST/
cp scripts/my-practice-update-client-tags.service $DEST/
cp scripts/my-practice-update-client-tags.timer   $DEST/
cp scripts/my-practice-fetch-calendar-events.service $DEST/
cp scripts/my-practice-fetch-calendar-events.timer   $DEST/

# Edit WorkingDirectory / ExecStart in each .service to match the actual repo path, then:
systemctl --user daemon-reload
systemctl --user enable --now my-practice-backup.timer
systemctl --user enable --now my-practice-update-client-tags.timer
systemctl --user enable --now my-practice-fetch-calendar-events.timer
```

### Check status

```bash
systemctl --user list-timers --all | grep my-practice
journalctl --user -u my-practice-backup.service -n 20
journalctl --user -u my-practice-update-client-tags.service -n 20
journalctl --user -u my-practice-fetch-calendar-events.service -n 20
```

## 📤 External Backups

The system creates backups in `$PAYMENTS_DATA_DIR/backups/` (outside the repository).
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
3. **Restore latest backup**: `./scripts/restore.sh backups/db_backup_LATEST.sql.gz backups/media_backup_LATEST.tar.gz`
4. **Restart Django**: `docker compose restart django`
5. **Verify**: Open http://localhost:8000 and check data

## 💡 Tips

- **Before major changes**: Always run `./scripts/backup.sh` manually
- **Before Django migrations**: Create a backup
- **Test regularly**: Perform a restore on a test system monthly
- **Monitoring**: Check `backups/backup.log` for errors
- **Retention**: Default 30 days, configurable in `backup.sh` (line 67)
