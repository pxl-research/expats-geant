# Dockerfile for Cue Service
# Privacy-first answer suggestion service with RAG pipeline

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Pre-download ChromaDB embedding model so it is baked into the image
# (avoids a ~80 MB download on first request at runtime)
RUN python3 -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; DefaultEmbeddingFunction()(['warmup'])"

# Copy application code
COPY cue_api/ ./cue_api/
COPY m_shared/ ./m_shared/
COPY run_api.py ./run_api.py

# Create directories for session data and logs
RUN mkdir -p /app/data/sessions /app/data/chroma /app/logs

# Run as non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"

# Run application
CMD ["python3", "run_api.py"]
