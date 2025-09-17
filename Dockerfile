# Multi-stage build for sf-gov-insight
FROM python:3.13-slim as backend-base

# Install system dependencies needed for crawl4ai and other packages
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for Chromium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_PATH=/usr/bin/chromium

WORKDIR /app

# Copy Python requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY agent/ ./agent/
COPY backend/ ./backend/
COPY ingest/ ./ingest/
COPY scraper/ ./scraper/
COPY demos/ ./demos/
COPY pyproject.toml .
COPY Makefile .
COPY dev.sh .

# Frontend build stage
FROM node:20-slim as frontend-build

WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci

COPY web/ ./
RUN npm run build

# Final production stage
FROM backend-base as production

# Copy built frontend assets
COPY --from=frontend-build /app/web/dist ./web/dist

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
