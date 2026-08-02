FROM python:3.11-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl pkg-config libcairo2-dev \
    libreoffice-writer libreoffice-calc \
    fonts-dejavu fonts-liberation fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .
COPY . .
RUN useradd -u 10001 -m app && chown -R app /app
# LibreOffice headless writes its profile to $HOME; Docker does not set HOME
# when USER changes, so set it explicitly or soffice --convert-to fails.
ENV HOME=/home/app
USER app
EXPOSE 8000

# ─── dev target: hot-reload, no migration gate, no healthcheck ─────────────
FROM base AS dev
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ─── prod target: migrate-on-boot, gunicorn workers, healthcheck ──────────
FROM base AS prod
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1
CMD ["sh", "-c", "alembic upgrade head && gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-2} -b 0.0.0.0:8000 --access-logfile - --error-logfile -"]
