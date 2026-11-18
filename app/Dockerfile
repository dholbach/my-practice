# ── Stage 1: compile Tailwind CSS ────────────────────────────────────────────
FROM node:26-slim AS css-builder
WORKDIR /app

# Install deps first so this layer is cached unless package.json/lock changes
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

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
FROM python:3.15-slim AS python-builder
WORKDIR /app

# Every apt step mounts the apt cache and drops Debian's docker-clean hook, which
# deletes each .deb after install and would leave the cache empty. A retry after a
# dropped connection then only fetches the packages it is still missing.
#
# gcc, libffi-dev, zlib1g-dev, libjpeg-dev, libopenjp2-7-dev: needed to compile
# Pillow from source where no pre-built wheel matches the platform and Python
# version. psycopg[binary] and cryptography ship prebuilt wheels, so no
# libpq-dev is needed here.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean \
    && apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    zlib1g-dev \
    libjpeg-dev \
    libopenjp2-7-dev

COPY requirements.txt .
# google-api-python-client bundles a static discovery JSON for every Google
# API it supports (586 files, ~98MB) — this app only ever calls
# build("calendar", "v3", ...), so all but that one file are dead weight.
# The pip cache mount lives outside the image layers: a rebuild after a changed
# pin (or a dropped connection) only downloads what it doesn't already have.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.txt \
    && find /install -path '*/discovery_cache/documents/*.json' ! -name 'calendar.v3.json' -delete

# ── Stage 3: production image ────────────────────────────────────────────────
FROM python:3.15-slim AS production
WORKDIR /app

# Runtime-only system dependencies for WeasyPrint, Ghostscript and Pillow.
# libjpeg62-turbo/libopenjp2-7/zlib1g are the runtime counterparts of the
# -dev headers used to compile Pillow in the python-builder stage above.
# postgresql-client is intentionally NOT installed here — it's only used by
# `./dev.py psql`/`./dev.py sql`, which run against the development image.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean \
    && apt-get update && apt-get install -y --no-install-recommends \
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
    gettext

RUN --mount=type=cache,target=/root/.cache/pip pip install --upgrade pip
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
# Node.js 26 (same major as the css-builder stage) for CSS rebuilding (npm run watch:css) and JS tests
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean \
    && apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && curl -fsSL https://deb.nodesource.com/setup_26.x | bash - \
    && apt-get install -y --no-install-recommends nodejs
RUN --mount=type=cache,target=/root/.npm npm install

# Dev Python dependencies (requirements-dev.txt already present from COPY . .).
# This layer sits above the app source, so any code change reruns it; the cache
# mounts keep that rerun from re-downloading every package.
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements-dev.txt
