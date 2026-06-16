# P-022: Media + Backups außerhalb Repo

**Status**: DONE (März 2026)

## Ziel

Media-Dateien (Klientendokumente, Logos, Signaturen) und Backups werden außerhalb
des Git-Repos gespeichert — kein versehentliches Einchecken von Binärdaten oder PII.

## Durchgeführt

### Media
- `MEDIA_ROOT` auf ein Verzeichnis außerhalb des Repo-Ordners konfiguriert
  (z.B. `/path/to/your/my-practice-data/media/`)
- `.gitignore` schließt `app/media/` aus
- Docker-Volume mountet das externe Media-Verzeichnis in den Container

### Backups
- Backup-Skript (`scripts/backup.sh`) sichert PostgreSQL-Dump + Media-Ordner
- Zielverzeichnis außerhalb des Repos (konfigurierbar via Env-Variable)
- Systemd-Timer (`payments-backup.timer`) läuft täglich um 00:00 Uhr
- `BACKUP_DIR` in `.env` konfiguriert

## Konfiguration
```env
MEDIA_ROOT=/path/to/your/my-practice-data/media
BACKUP_DIR=/path/to/your/my-practice-data/backups
```

## Ergebnis
- Keine Binärdaten im Git-Repo
- Regelmäßige automatische Backups aktiv
- Restore-Prozess dokumentiert in [docs/development/BACKUP_SETUP.md](../development/BACKUP_SETUP.md)
