FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY shape_ui/requirements.txt .
RUN pip install -r requirements.txt

COPY shape_ui/ ./shape_ui/
COPY m_shared/ ./m_shared/

# Run as non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8004

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=5s \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8004/health')"

CMD ["python3", "-m", "uvicorn", "shape_ui.main:app", "--host", "0.0.0.0", "--port", "8004"]
