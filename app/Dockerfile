# ── Stage 1: compile Tailwind CSS ────────────────────────────────────────────
FROM node:26-slim AS css-builder
WORKDIR /app

# Install deps first so this layer is cached unless package.json/lock changes
COPY package.json package-lock.json ./
RUN npm ci

# Only the files Tailwind's @source directives scan
COPY static/css/tailwind.css static/css/tailwind.css
COPY static/js/ static/js/
COPY templates/ templates/

RUN npm run build:css

# Assemble the rest of the app source here too, and drop the Tailwind source
# file now — Docker layers are additive, so COPY-then-RUN-rm in the stage
# that ships would still leave the removed file's bytes in an earlier layer.
# Doing it in this discarded builder stage means it never lands in the image.
COPY . .
RUN rm static/css/tailwind.css

# ── Stage 2: compile Python dependencies ─────────────────────────────────────
# Isolated so the compiler toolchain (gcc + dev headers) never lands in the
# final image — only the compiled packages get copied over.
FROM python:3.14-slim AS python-builder
WORKDIR /app

# gcc, libffi-dev, zlib1g-dev, libjpeg-dev, libopenjp2-7-dev: needed to compile
# Pillow from source on Python 3.14 (no pre-built cp314 wheels available yet
# for all platforms). psycopg[binary] and cryptography ship prebuilt wheels,
# so no libpq-dev is needed here.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    zlib1g-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# google-api-python-client bundles a static discovery JSON for every Google
# API it supports (586 files, ~98MB) — this app only ever calls
# build("calendar", "v3", ...), so all but that one file are dead weight.
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt \
    && find /install -path '*/discovery_cache/documents/*.json' ! -name 'calendar.v3.json' -delete

# ── Stage 3: production image ────────────────────────────────────────────────
FROM python:3.14-slim AS production
WORKDIR /app

# Runtime-only system dependencies for WeasyPrint, Ghostscript and Pillow.
# libjpeg62-turbo/libopenjp2-7/zlib1g are the runtime counterparts of the
# -dev headers used to compile Pillow in the python-builder stage above.
# postgresql-client is intentionally NOT installed here — it's only used by
# `./dev.py psql`/`./dev.py sql`, which run against the development image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    fonts-liberation \
    curl \
    libjpeg62-turbo \
    libopenjp2-7 \
    zlib1g \
    ghostscript \
    gettext \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
COPY --from=python-builder /install /usr/local

# App source, already including the compiled CSS and minus the Tailwind
# source file — assembled in the css-builder stage (see the comment there).
COPY --from=css-builder /app /app

RUN chmod +x manage.py

# Compile translation catalogs into binary .mo files
RUN python manage.py compilemessages

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "config.wsgi:application"]

# ── Stage 4: development image (extends production) ──────────────────────────
FROM production AS development

# postgresql-client: only needed for `./dev.py psql`/`./dev.py sql`, which
# exec into this (development-target) container — not shipped in production.
# Node.js 22 (LTS) for CSS rebuilding (npm run watch:css) and JS tests
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*
RUN npm install

# Dev Python dependencies (requirements-dev.txt already present from COPY . .)
RUN pip install --no-cache-dir -r requirements-dev.txt
