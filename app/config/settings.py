"""
Django settings for payments project.
"""

import os
from pathlib import Path

from django.utils.csp import CSP
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-dev-key-change-in-production")

# Fernet key for encrypting Art. 9 DSGVO clinical fields (P-009).
# None in dev/test — encrypted fields will raise if accessed without a key,
# but migrations and model definitions work without it.
FERNET_KEY: str | None = os.getenv("FERNET_KEY")

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
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "config.middleware.PracticeScopeMiddleware",  # Set current practice in request
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
            ],
            # Disable template caching in DEBUG mode for instant updates
            "debug": DEBUG,
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database - using existing PostgreSQL
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "n8n"),
        "USER": os.getenv("POSTGRES_USER", "n8n"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "n8n_password"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
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
LANGUAGE_CODE = "de-de"
TIME_ZONE = "Europe/Berlin"
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

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Persistent data directory (bind-mounted from host; contains static documents like .docx templates)
PAYMENTS_DATA_DIR = Path(
    os.environ.get("MY_PRACTICE_DATA_DIR", str(BASE_DIR.parent / "my-practice-data"))
)

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Logging configuration
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
        },
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
    EMAIL_TIMEOUT = 10  # Fail fast if Proton Bridge is unreachable
else:
    # Development: print emails to console
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Google Calendar API configuration
GOOGLE_CALENDAR_CLIENT_ID = os.environ.get("GOOGLE_CALENDAR_CLIENT_ID", "")
GOOGLE_CALENDAR_CLIENT_SECRET = os.environ.get("GOOGLE_CALENDAR_CLIENT_SECRET", "")

# Content Security Policy
# Phase 2: script-src uses nonce (no unsafe-inline for scripts).
# style-src keeps unsafe-inline: ~809 inline style="" attrs throughout templates
# would need auditing before removing it; removing style-src unsafe-inline
# breaks chart containers (height: Xpx), tables, logo sizing, etc.
# script-src: CSP.NONCE investigated but non-functional — request.csp_nonce renders
# as empty string and no 'nonce-...' token appears in the outgoing CSP header.
# Restored unsafe-inline for scripts. Key security win remains: all external scripts
# are vendored locally (no CDN), so CSP blocks any injected external script sources.
# Nonce-based script-src is deferred to M-11 Phase 3.
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [
        CSP.SELF,
        CSP.UNSAFE_INLINE,
        CSP.UNSAFE_EVAL,
    ],  # unsafe-eval required by Alpine.js (new Function()); nonce deferred Phase 3
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE],  # unsafe-inline needed for style="" attrs
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

    # HSTS (HTTP Strict Transport Security) — only meaningful with HTTPS
    if SECURE_SSL_REDIRECT:
        SECURE_HSTS_SECONDS = 31536000  # 1 year
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True

    # Security headers
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
DEFAULT_EXCEPTION_REPORTER_FILTER = "config.exception_reporter.PIIExceptionReporterFilter"
