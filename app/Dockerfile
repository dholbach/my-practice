FROM python:3.14-slim

WORKDIR /app

# Install system dependencies including WeasyPrint requirements
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
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (for JavaScript tests)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Install Tailwind CSS CLI + framework globally so both survive the app volume mount.
# NODE_PATH lets the CLI resolve the tailwindcss package from its global install path.
RUN npm install -g @tailwindcss/cli tailwindcss
ENV NODE_PATH=/usr/lib/node_modules

# Copy application
COPY . .

# Make manage.py executable
RUN chmod +x manage.py

# Collect static files (will be done at runtime)
# RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Start Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "config.wsgi:application"]
