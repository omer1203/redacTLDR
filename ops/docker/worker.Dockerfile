# Worker container image for Celery task execution.
FROM python:3.11-slim

# Keep repository under /app for package-qualified imports.
WORKDIR /app

# Worker runtime dependencies only; keep API/dev packages out of this image.
COPY requirements-worker.txt .

RUN pip install --no-cache-dir --upgrade pip setuptools \
    && pip install --no-cache-dir -r requirements-worker.txt \
    && useradd --system --uid 10001 --no-create-home app

# Copy worker/API shared source tree.
COPY . .
USER app

# Solo pool is set in compose. Bytecode stays out of the writable layer.
ENV PYTHONPATH=/app \
    HOME=/tmp \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Listen on `default` (API producer) and `celery` (older backlog messages).
CMD ["celery", "-A", "services.worker.app.celery_app.celery", "worker", "-Q", "default,celery", "--loglevel=INFO"]
