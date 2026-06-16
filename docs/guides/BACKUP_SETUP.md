# Backup Setup

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

## Install System Services

## Quick Install

Run this command to install system services (automatic backups and app auto-start):

```bash
sudo bash scripts/install-system-jobs.sh
```

This will:
3. Enable the app auto-start service (starts during boot after network/docker readiness)
2. Enable the backup timer (daily, randomized execution window)
3. Enable the app auto-start service (starts 2 minutes after boot)
4. Start the backup timer immediately
5. Show you the status and next scheduled run

## Manual Installation Steps

If you prefer to install manually:

```bash
journalctl -u my-practice-backup.service -f
sudo cp scripts/my-practice-backup.service /etc/systemd/system/
sudo cp scripts/my-practice-backup.timer /etc/systemd/system/
sudo cp scripts/my-practice-app.service /etc/systemd/system/

# 2. Reload systemd
sudo systemctl daemon-reload

# 3. Enable and start the services
sudo systemctl enable my-practice-backup.timer
sudo systemctl start my-practice-backup.timer
sudo systemctl enable my-practice-app.service

# 4. Check status
systemctl status my-practice-backup.timer
systemctl status my-practice-app.service
```

## Verify Installation

```bash
# Check when next backup will run
systemctl list-timers my-practice-backup.timer

# View backup logs
journalctl -u my-practice-backup.service -f

# Run a manual test backup
./scripts/backup.sh
```

Note for laptop use (not permanently online):
- Backup and tag-update timers run `daily` with `RandomizedDelaySec=12h`.
- This spreads execution across the day (not always the same time).
- `Persistent=true` ensures missed runs are caught up at the next online start.

## Management Commands

### Backup Timer

Note: `my-practice-backup.service` is a timer-driven oneshot unit and should **not** be enabled directly.
Use `enable/disable` only for `my-practice-backup.timer`.

```bash
# Stop automatic backups
sudo systemctl stop my-practice-backup.timer

# Disable automatic backups (won't start on reboot)
sudo systemctl disable my-practice-backup.timer

# Re-enable
sudo systemctl enable --now my-practice-backup.timer

# View service logs
journalctl -u my-practice-backup.service -f
```

### App Auto-Start

```bash
# Start app manually
sudo systemctl start my-practice-app.service

# Stop app
sudo systemctl stop my-practice-app.service

# Disable auto-start on boot
sudo systemctl disable my-practice-app.service

# Re-enable auto-start
sudo systemctl enable my-practice-app.service

# View service logs
journalctl -u my-practice-app.service -f
```

## Troubleshooting

If backups aren't running:

1. Check timer is active: `systemctl is-active my-practice-backup.timer`
2. Check for errors: `journalctl -u my-practice-backup.service -n 50`
3. Verify Docker is running: `docker ps`
4. Test manual backup: `./scripts/backup.sh`

If you encounter SELinux errors like `status=203/EXEC` or `execute-access on backup.sh`:

1. Ensure that `my-practice-backup.service` calls the script via bash:
	- `ExecStart=/usr/bin/env bash /path/to/payments/scripts/backup.sh`
2. Reload the unit and restart the service:

```bash
sudo systemctl daemon-reload
sudo systemctl restart my-practice-backup.service
sudo systemctl status my-practice-backup.service --no-pager
```

## Bluefin Notes (Immutable Host)

Yes, on Bluefin `/etc/systemd/system/` is the correct location for custom system units.
This configuration survives `rpm-ostree` updates.

If you encounter errors like `status=203/EXEC` or `Permission denied` for `dev.py`:

1. Update the unit file (use Python explicitly + run as user):
	- `User=<your-username>`
	- `ExecStart=/usr/bin/env python3 /path/to/payments/dev.py start`
2. Reload systemd and restart the service:

```bash
sudo systemctl daemon-reload
sudo systemctl restart my-practice-app.service
sudo systemctl status my-practice-app.service --no-pager
```

If you prefer to avoid root, a user service under `~/.config/systemd/user/` is also possible.
However, for auto-start on boot (without login), the system unit in `/etc/systemd/system/`
is the better choice.
