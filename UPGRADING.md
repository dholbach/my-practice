# Upgrading

This document is for self-hosters moving from one version to the next. For first-time setup see [GETTING_STARTED.md](docs/guides/GETTING_STARTED.md).

## Image-based upgrade (recommended)

Uses the pre-built image from GHCR — no build toolchain needed on the host.

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

Migrations run automatically on startup. That's it in the normal case.

### Common management commands

```bash
# Create the first admin user
docker compose -f docker-compose.prod.yml exec django python manage.py createsuperuser

# Run any Django management command
docker compose -f docker-compose.prod.yml exec django python manage.py <command>

# Open a Django shell
docker compose -f docker-compose.prod.yml exec django python manage.py shell
```

## Source-based upgrade

For dev setups that run from a local clone:

```bash
git pull
./dev.py restart --force   # rebuilds image, reloads .env
./dev.py manage migrate    # applies any new database migrations
```

That's it in the normal case. If a release has additional steps — config changes, data migrations, removed settings — they are documented in the version section below.

## Breaking changes by version

### v0.1.0 → next

No breaking changes documented yet. Check back when the next release is tagged.

## Versioning policy

Releases follow [semantic versioning](https://semver.org/):

- **Patch** (`v0.1.x`) — bug fixes and dependency updates; always safe to apply
- **Minor** (`v0.x.0`) — new features; backwards-compatible; run migrations
- **Major** (`vX.0.0`) — breaking changes; read the version section below before upgrading

Breaking changes that require manual intervention (config renames, removed fields, changed env vars) are always called out explicitly in the relevant version section above.
