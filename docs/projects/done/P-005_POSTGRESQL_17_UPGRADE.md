# P-005: PostgreSQL 17 Upgrade

**Status**: ✅ DONE
**Completed**: 3. März 2026
**Effort**: ~1h (dump/restore Methode)
**Technical Guide**: [docs/development/POSTGRESQL_17_UPGRADE.md](../../development/POSTGRESQL_17_UPGRADE.md)

## Ergebnis

Upgrade von PostgreSQL 15 auf 17 erfolgreich abgeschlossen.

## Durchgeführte Schritte

1. **Backup**: `pg_dump` vor Upgrade gesichert
   - Datei: `backups/pre_pg17_upgrade_20260303_142713.sql` (544k)
2. **Container stoppen** + altes Volume löschen: `docker volume rm payments_postgres_data`
3. **Image tauschen**: `postgres:15-alpine` → `postgres:17-alpine` in docker-compose.yml
4. **Neues Volume starten**: `docker compose up -d postgres`
5. **Restore**: Dump in neues PG17-Volume eingespielt
6. **Verifiziert**: 676 Invoices, 113 Clients, 1829 Items, Superuser erhalten
7. **Tests**: Alle Django + JS Tests bestanden auf PostgreSQL 17.9

## Erzielte Benefits

- PostgreSQL 17.9 (Alpine) läuft stabil
- Alle Daten vollständig erhalten
- Upgrade in < 1h abgeschlossen (kein dediziertes Maintenance Window nötig)
- Basis für zukünftige PG-Features (JSON, parallele Queries)

## Related

- Root: [PROJECTS.md](../../../PROJECTS.md#p-005-postgresql-17-upgrade)
