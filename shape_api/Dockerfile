FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ gosu \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY shape_api/ ./shape_api/
COPY m_shared/ ./m_shared/
COPY cue_api/ ./cue_api/
COPY run_chat_api.py ./run_chat_api.py

RUN mkdir -p /app/data/sessions /app/logs

# Create non-root user (entrypoint drops to this user via gosu)
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser \
    && chown -R appuser:appuser /app

COPY shape_api/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8802

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8802/health')"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "run_chat_api.py"]
