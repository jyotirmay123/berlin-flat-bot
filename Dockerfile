FROM python:3.11-slim

# tzdata is required by zoneinfo for Europe/Berlin DST-aware times.
# gcc is needed to compile aiosqlite / greenlet wheels that lack a pre-built binary.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.5

COPY pyproject.toml poetry.lock ./

# Install production deps into the system Python (no virtualenv inside container).
# Playwright browsers are NOT installed — ScrapFly handles IS24; the package itself
# is safe to import without browser binaries.
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --only main --no-interaction

COPY bot/ ./bot/

# /data is the mount point for the Fly.io persistent volume (SQLite lives here).
# /app/logs is for the rotating log file (ephemeral — stdout is the main log channel).
RUN mkdir -p /data /app/logs

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "bot.main"]
