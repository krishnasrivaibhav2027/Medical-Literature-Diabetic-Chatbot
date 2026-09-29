# syntax=docker/dockerfile:1

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_HOME=/app/model_cache \
    PORT=8080

WORKDIR /app

# Install system dependencies needed for compiling C extensions & postgres client
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Create model cache directory with appropriate structure
RUN mkdir -p /app/model_cache

# Copy application source code
COPY backend /app/backend

# Create a non-root system user for security compliance on Google Cloud Run
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose standard Cloud Run port
EXPOSE 8080

# Run uvicorn server binding to 0.0.0.0 and dynamic $PORT passed by Cloud Run
CMD exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}
