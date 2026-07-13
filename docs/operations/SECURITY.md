# Security Configuration

## Environment Variables

The project uses `python-dotenv` for environment variables. A `.env` file in the root directory
is loaded automatically.

### Development Setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Adjust the values in `.env` (especially the database password)

### Required Environment Variables

#### Django Core
- `DJANGO_SECRET_KEY`: Secret key for Django (at least 50 characters, random)
- `DJANGO_DEBUG`: `True` for development, `False` for production
- `DJANGO_ALLOWED_HOSTS`: Comma-separated list of allowed hosts (e.g. `example.com,www.example.com`)

#### Database
- `POSTGRES_DB`: Database name (default: `my_practice`)
- `POSTGRES_USER`: Database user (default: `my_practice`)
- `POSTGRES_PASSWORD`: Database password (CHANGE THIS!)
- `POSTGRES_HOST`: Database host (default: `localhost`)
- `POSTGRES_PORT`: Database port (default: `5432`)

#### Email (Optional - Proton Bridge)
- `USE_PROTON_BRIDGE`: `true` to enable SMTP
- `EMAIL_HOST`: SMTP host (default: `127.0.0.1`)
- `EMAIL_PORT`: SMTP port (default: `1025`)
- `EMAIL_HOST_USER`: Proton email address
- `EMAIL_HOST_PASSWORD`: Proton Bridge password
- `DEFAULT_FROM_EMAIL`: Sender email address

#### Google Calendar (Optional)
- `GOOGLE_CALENDAR_CLIENT_ID`: OAuth2 client ID
- `GOOGLE_CALENDAR_CLIENT_SECRET`: OAuth2 client secret

## Production Security Checklist

### Before Deployment

1. **Generate secret key**:
   ```python
   from django.core.management.utils import get_random_secret_key
   print(get_random_secret_key())
   ```

2. **Set environment variables**:
   ```bash
   DJANGO_SECRET_KEY=<generated-secret-key>
   DJANGO_DEBUG=False
   DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
   POSTGRES_PASSWORD=<secure-random-password>
   ```

3. **Run security check**:
   ```bash
   ./dev.py manage check --deploy
   ```
   Should show no errors (warnings in development are normal).

### Automatic Production Security Settings

When `DEBUG=False`, the following are automatically enabled:

- ✅ **HTTPS Redirect**: `SECURE_SSL_REDIRECT = True`
- ✅ **Secure Cookies**: `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`
- ✅ **HSTS**: `SECURE_HSTS_SECONDS = 31536000` (1 year)
- ✅ **Security Headers**:
  - `SECURE_CONTENT_TYPE_NOSNIFF = True`
  - `SECURE_BROWSER_XSS_FILTER = True`
  - `X_FRAME_OPTIONS = "DENY"`

### Database Constraints

- ✅ **Invoice Number Uniqueness**: DB-level constraint prevents duplicates
  - Model: `unique=True` on `invoice_number`
  - DB: `UniqueConstraint` for additional safety
  - Error: German error text on violation (UI language is German)

### Additional Security Measures

#### PII Commit Guard (pre-commit)
- `scripts/check_pii.py` runs in the pre-commit hook and blocks commits whose
  staged changes contain terms from a **local, untracked denylist**
- Denylist location: `.git/pii-denylist` (one term per line, `#` comments,
  case-insensitive substring match) — it holds the sensitive strings themselves,
  so it must never be committed; keeping it inside `.git/` makes that impossible
- No denylist present → the check passes silently (contributors are unaffected)
- Full-tree audit: `python3 scripts/check_pii.py --all`
- Populate it with real client names, payer names, addresses, and distinctive
  client codes for your own installation

#### Static Files
- Production uses WhiteNoise with `CompressedManifestStaticFilesStorage`
- Development uses simple storage (no caching)

#### Middleware
- CSRF Protection enabled (`CsrfViewMiddleware`)
- Clickjacking Protection (`XFrameOptionsMiddleware`)
- Security Middleware for HTTPS/headers (`SecurityMiddleware`)

#### Logging
- Email backend logs to console (DEBUG level)
- Configurable in `settings.py` → `LOGGING`

## HTTPS Setup

### Local Development
No HTTPS needed (DEBUG=True disables HTTPS enforcing).

### Production
1. **SSL certificate**: Use Let's Encrypt (free, automatic)
2. **Reverse proxy**: Nginx/Caddy terminates HTTPS
3. **Django**: HSTS is set automatically when DEBUG=False

### Reverse Proxy Example (Nginx)
```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /path/to/payments/app/staticfiles/;
    }

    location /media/ {
        # Media files live outside the repo under $MY_PRACTICE_DATA_DIR/media/
        alias /path/to/payments-data/media/;
    }
}
```

## Backup & Disaster Recovery

See [BACKUP_SETUP.md](BACKUP_SETUP.md) for:
- Automatic backups (DB + media)
- Retention policy (30 days rolling)
- Restore process

## Security Audit

Run periodically:

```bash
# Django security check
./dev.py manage check --deploy

# Python dependency check
pip list --outdated

# Database integrity
./dev.py manage verify_session_alignment
```

## Further Resources

- [Django Security Checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Let's Encrypt](https://letsencrypt.org/)
