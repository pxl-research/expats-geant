# Dockerfile for M-UI Survey Review Frontend

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY cue_ui/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY cue_ui/ ./cue_ui/

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')"

CMD ["python3", "-m", "uvicorn", "cue_ui.main:app", "--host", "0.0.0.0", "--port", "8002"]
