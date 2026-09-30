# API container image for FastAPI runtime.
# Uses slim base to keep build size reasonable.
FROM python:3.11-slim

# All paths below are relative to repository root copied into /app.
WORKDIR /app

# Install API runtime dependencies first to leverage Docker layer caching.
COPY requirements-api.txt .

RUN pip install --no-cache-dir -r requirements-api.txt

# Copy monorepo sources (API imports from package-qualified paths).
COPY . .

# keep repo root importable for package-qualified imports
ENV PYTHONPATH=/app

# FastAPI/uvicorn listens on 8000 in this image.
EXPOSE 8000

# Start API server.
CMD ["uvicorn", "services.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
