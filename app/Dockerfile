# ── Stage 1: compile Tailwind CSS ───────────────────────────────────────────
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

# ── Stage 2: production image ────────────────────────────────────────────────
FROM python:3.14-slim AS production
WORKDIR /app

# System dependencies for WeasyPrint and psycopg
# zlib1g-dev, libjpeg-dev, libopenjp2-7-dev: needed to compile Pillow from source on Python 3.14
# (no pre-built cp314 wheels available yet for all platforms)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    libffi-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    fonts-liberation \
    curl \
    zlib1g-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    ghostscript \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# Production Python dependencies only
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy application and drop in the compiled CSS from the builder stage
COPY . .
COPY --from=css-builder /app/static/css/tailwind.out.css static/css/tailwind.out.css
# Remove the Tailwind source file — only the compiled output is served
RUN rm static/css/tailwind.css

RUN chmod +x manage.py

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "config.wsgi:application"]

# ── Stage 3: development image (extends production) ──────────────────────────
FROM production AS development

# Node.js 22 (LTS) for CSS rebuilding (npm run watch:css) and JS tests
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*
RUN npm install

# Dev Python dependencies (requirements-dev.txt already present from COPY . .)
RUN pip install --no-cache-dir -r requirements-dev.txt
