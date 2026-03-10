FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY m_chat_ui/requirements.txt .
RUN pip install -r requirements.txt

COPY m_chat_ui/ ./m_chat_ui/

EXPOSE 8004

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=5s \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8004/health')"

CMD ["python3", "-m", "uvicorn", "m_chat_ui.main:app", "--host", "0.0.0.0", "--port", "8004"]
