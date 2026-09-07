FROM python:3.13-slim

ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# System deps:
#   gcc libpq-dev  — build psycopg2
#   nodejs npm     — required by Lighthouse CLI (Node ≥18, Debian Bookworm default is fine)
#   chromium       — headless Chrome for Lighthouse; pulls all required shared libs
#   npm install -g lighthouse — installs the lighthouse CLI used by services/lighthouse.py
#   CHROME_PATH    — tells Lighthouse where to find the Chromium binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    nodejs npm \
    chromium \
    && npm install -g lighthouse \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_PATH=/usr/bin/chromium

# Install dependencies first (cached layer)
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-install-project

# Copy source and install project
COPY . .
RUN uv sync --frozen

EXPOSE 8000

ENTRYPOINT ["sh", "entrypoint.sh"]
