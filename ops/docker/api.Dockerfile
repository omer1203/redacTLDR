# API container image for FastAPI runtime.
# Uses slim base to keep build size reasonable.
FROM python:3.11-slim

# All paths below are relative to repository root copied into /app.
WORKDIR /app

# Install API runtime dependencies first to leverage Docker layer caching.
COPY requirements-api.txt .

RUN pip install --no-cache-dir --upgrade pip setuptools \
    && pip install --no-cache-dir -r requirements-api.txt \
    && useradd --system --uid 10001 --no-create-home app

# Copy monorepo sources (API imports from package-qualified paths).
COPY . .
USER app

# One process. Bytecode stays out of the image layer and logs stay unbuffered.
ENV PYTHONPATH=/app \
    HOME=/tmp \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# FastAPI/uvicorn listens on 8000 in this image.
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/v1/health')" || exit 1

# Start API server.
CMD ["uvicorn", "services.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
