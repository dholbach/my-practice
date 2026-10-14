"""
Django settings for payments project.
"""

import os
import sys
import tempfile
from pathlib import Path

from django.utils.csp import CSP
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Used both for logging noise suppression (below) and to keep test runs from
# writing real uploaded files into the bind-mounted host media directory
# (see MEDIA_ROOT) — TestCase rolls back DB rows on teardown but has no way
# to undo a FileField's actual filesystem write, so without this every test
# run that uploads an image leaves an orphaned file behind in production
# storage.
# "PYTEST_VERSION" covers `./dev.py test --smart` (pytest-testmon), which
# never puts "test" in sys.argv.
RUNNING_TESTS = "test" in sys.argv or "PYTEST_VERSION" in os.environ

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-dev-key-change-in-production")

# Fernet key(s) for the encrypted fields (clinical records, client and inquiry
# notes, calendar credentials). Comma-separated for rotation: the first key
# encrypts, all of them decrypt — see my_practice/fields.py. A missing key is
# a system-check warning (an error under --deploy).
FERNET_KEY: str | None = os.getenv("FERNET_KEY")
if RUNNING_TESTS and not FERNET_KEY:
    # A fixed throwaway key, so the suite exercises encryption on a clean
    # checkout instead of passing only where a developer .env exports one.
    FERNET_KEY = "7zIJPIlZkdMSPifNsPuNBjIAIqiUkFHmRJN8HGG8ytQ="  # gitleaks:allow

DEBUG = os.getenv("DJANGO_DEBUG", "False") == "True"

# Security: scrub PII from 500 error reports and tracebacks
DEFAULT_EXCEPTION_REPORTER_FILTER = "config.exception_reporter.PIIExceptionReporterFilter"

# Security: Parse ALLOWED_HOSTS from environment
# Format: "localhost,127.0.0.1,example.com" or "*" for dev
ALLOWED_HOSTS_ENV = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
if ALLOWED_HOSTS_ENV == "*":
    ALLOWED_HOSTS = ["*"]  # Only for development!
else:
    ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_ENV.split(",") if host.strip()]

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "my_practice",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Static files with Gunicorn
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "config.middleware.PracticeScopeMiddleware",  # Set current practice in request
    "config.middleware.TwoFactorRequiredMiddleware",  # Only with REQUIRE_TWO_FACTOR
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Disable caching in development
if DEBUG:
    MIDDLEWARE.insert(0, "config.middleware.NoCacheMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "my_practice.context_processors.update_check",
                "django.template.context_processors.i18n",
                # Puts csp_nonce in the context for <script nonce="{{ csp_nonce }}">;
                # without it the nonce renders empty (see SECURE_CSP below).
                "django.template.context_processors.csp",
            ],
            # Disable template caching in DEBUG mode for instant updates
            "debug": DEBUG,
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "my_practice"),
        "USER": os.getenv("POSTGRES_USER", "my_practice"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

# Cache
#
# Without this block Django falls back to per-process LocMemCache: each gunicorn
# worker warms its own copy and every restart starts cold. The only thing cached
# today is the GitHub release lookup in context_processors.update_check, which
# runs on every authenticated page render — so a cold or per-worker cache means
# that outbound call happens far more often than its 24-hour TTL implies.
#
# The database backend is the one that needs no extra service. Its table is
# created by migration 0032 rather than a manual `createcachetable`, so there is
# no new deploy step: it appears wherever `migrate` already runs.
if RUNNING_TESTS:
    # LocMem under tests: no DB round-trips, and each process gets a clean cache
    # rather than values bleeding between tests through a shared table.
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "my_practice_cache",
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = os.getenv("DJANGO_LANGUAGE_CODE", "de-de")
LANGUAGES = [
    ("de", "Deutsch"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "Europe/Berlin")
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# WhiteNoise configuration for static files with Gunicorn
# In DEBUG mode, use simple storage (no manifest, no compression)
# In production, use compressed manifest storage for optimal performance
if DEBUG:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

# Auth
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# Sessions end after this long without a request (sliding: every request
# renews it), instead of Django's fixed two weeks. A forgotten open tab on a
# shared or lost laptop should not stay signed in to health data for days.
# Default 8 hours, i.e. a working day; DJANGO_SESSION_IDLE_HOURS overrides it.
SESSION_COOKIE_AGE = int(os.getenv("DJANGO_SESSION_IDLE_HOURS", "8")) * 3600
SESSION_SAVE_EVERY_REQUEST = True

# Require every user to set up an authenticator app (second sign-in factor)
# before using the app. Off by default; a hosted instance reachable from the
# internet should turn it on. See views/auth_views.py.
REQUIRE_TWO_FACTOR = os.getenv("REQUIRE_TWO_FACTOR", "false").lower() == "true"

# Tests don't need PBKDF2's deliberately slow iteration count — MD5 is
# insecure but fine for throwaway test users, and cuts time on every test
# that calls create_user()/set_password().
if RUNNING_TESTS:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = (
    Path(tempfile.mkdtemp(prefix="my-practice-test-media-"))
    if RUNNING_TESTS
    else BASE_DIR / "media"
)

# Persistent data directory (bind-mounted from host; contains static documents like .docx templates)
MY_PRACTICE_DATA_DIR = Path(
    os.environ.get("MY_PRACTICE_DATA_DIR", str(BASE_DIR.parent / "my-practice-data"))
)

# Backup files directory — fixed container-internal mount point (see docker-compose*.yml,
# which bind-mounts the host-side MY_PRACTICE_DATA_DIR/backups here).
BACKUP_DIR = "/app/backups"

# The dashboard warns when the newest backup in BACKUP_DIR is older than this
# many hours (daily timer with a 12h random delay, plus slack). 0 turns the
# check off — the default under DEBUG, where BACKUP_DIR is not mounted, and
# the setting for an installation that backs up some other way.
BACKUP_MAX_AGE_HOURS = int(os.getenv("BACKUP_MAX_AGE_HOURS", "0" if DEBUG else "48"))

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Logging configuration
#
# Without an explicit "root" entry, loggers not listed below (most of
# my_practice.*) have no configured handler and fall through to Python's
# logging.lastResort, which prints WARNING+ straight to stderr regardless of
# level. That's normally fine, but it means every test that deliberately
# exercises an error path (mocked exceptions, missing Ghostscript, invalid
# uploads, Django's own django.request logger emitting 4xx/5xx access
# warnings, ...) also prints noise to the test runner's output that reads
# like a failure even though the test passed.
#
# The level must be set on the *handler*, not just the logger: a record
# reaching root via propagation (e.g. from "django.request", which sets its
# own effective level via its "django" ancestor) is filtered by each
# handler's own level as it's emitted, not by root's logger-level attribute.
# A logger-only threshold has no effect on records the logger itself didn't
# originate.
_CONSOLE_LEVEL = "CRITICAL" if RUNNING_TESTS else "WARNING"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "level": _CONSOLE_LEVEL,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": _CONSOLE_LEVEL,
    },
    "loggers": {
        "django.core.mail": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "my_practice.email": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# Email configuration
# For development: console backend (prints to console)
# For production: SMTP via Proton Bridge
USE_PROTON_BRIDGE = os.environ.get("USE_PROTON_BRIDGE", "false").lower() == "true"

if USE_PROTON_BRIDGE:
    # Proton Bridge SMTP configuration
    # Use custom backend that accepts self-signed certificates
    EMAIL_BACKEND = "my_practice.email_backend.ProtonBridgeEmailBackend"
    EMAIL_HOST = os.environ.get("EMAIL_HOST", "127.0.0.1")
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "1025"))
    EMAIL_USE_TLS = True
    EMAIL_USE_SSL = False
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")  # Your Proton email
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")  # Proton Bridge password
    DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
    # 30s: a down/unreachable Bridge still fails almost instantly (connection
    # refused), but a live Bridge can take >10s to hand off to Proton's
    # servers before replying to DATA/QUIT — a short timeout here causes a
    # false "send failed" error even though the message was actually sent
    # (confirmed in the Proton Sent folder).
    EMAIL_TIMEOUT = 30
else:
    # Development: print emails to console
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Google Calendar API configuration
GOOGLE_CALENDAR_CLIENT_ID = os.environ.get("GOOGLE_CALENDAR_CLIENT_ID", "")
GOOGLE_CALENDAR_CLIENT_SECRET = os.environ.get("GOOGLE_CALENDAR_CLIENT_SECRET", "")

# Content Security Policy
# script-src: no 'unsafe-inline'. Inline <script> blocks carry
# nonce="{{ csp_nonce }}" (from the csp context processor above) and there are
# no inline on*= handlers — both enforced by tests/test_csp_coverage.py — so an
# injected <script> or onerror= attribute does not run. 'unsafe-eval' stays
# because Alpine.js evaluates x-* expressions with new Function(); dropping it
# needs Alpine's CSP build and rewriting those expressions. It also means
# injected markup carrying Alpine attributes (x-init="…") would still execute,
# so template autoescaping remains the primary XSS defence; CSP is the backstop.
# style-src keeps 'unsafe-inline' for style="" attributes and the inline styles
# Alpine/htmx set at runtime; styles cannot execute code.
# All scripts are vendored locally (no CDN), so 'self' covers every src=.
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE, CSP.UNSAFE_EVAL],
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE],
    "img-src": [CSP.SELF, "data:"],  # data: for base64 logos/signatures
    "connect-src": [CSP.SELF],  # AJAX/fetch calls
    "font-src": [CSP.SELF],
}

# Security settings for production
if not DEBUG:
    # HTTPS — disable when running behind a plain HTTP reverse proxy or on a local
    # network without TLS termination; enable when HTTPS is handled upstream.
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "false").lower() == "true"
    SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
    CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT

    if SECURE_SSL_REDIRECT:
        # gunicorn never terminates TLS itself, so HTTPS here always means a
        # reverse proxy in front. Without trusting its X-Forwarded-Proto every
        # request looks like plain HTTP: SECURE_SSL_REDIRECT redirects forever,
        # and the CSRF origin check rejects every form post (the browser sends
        # Origin: https://…, Django expects http://…). The proxy must set this
        # header itself, overwriting any client-supplied value — see SECURITY.md.
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

        # HSTS (HTTP Strict Transport Security) — only meaningful with HTTPS
        SECURE_HSTS_SECONDS = 31536000  # 1 year
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True

    # Security headers
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# Update check — context processor polls GitHub releases API (once per day, cached).
# Set UPDATE_CHECK_DISABLED=true in .env to opt out.
UPDATE_CHECK_DISABLED = os.environ.get("UPDATE_CHECK_DISABLED", "false").lower() == "true"
