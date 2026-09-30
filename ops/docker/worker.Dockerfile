# Worker container image for Celery task execution.
FROM python:3.11-slim

# Keep repository under /app for package-qualified imports.
WORKDIR /app

# Worker runtime dependencies only; keep API/dev packages out of this image.
COPY requirements-worker.txt .

RUN pip install --no-cache-dir -r requirements-worker.txt

# Copy worker/API shared source tree.
COPY . .

# Ensure `services.*` imports resolve at runtime.
ENV PYTHONPATH=/app

# No HTTP service exposed by worker; this is informational only.
EXPOSE 8000

# Listen on `default` (API producer) and `celery` (older backlog messages).
CMD ["celery", "-A", "services.worker.app.celery_app.celery", "worker", "-Q", "default,celery", "--loglevel=INFO"]
