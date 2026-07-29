FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    JSTUDY_JOBS_DIR=/app/data/jobs

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY apps ./apps
COPY packages ./packages
COPY web_mvp.py mvp_runner.py soul.md mnemonics.md rag-config.example.json ./

RUN mkdir -p /app/data/jobs

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=5).close()"

CMD ["python", "-m", "uvicorn", "apps.api.jstudy_api.app:app", "--host", "0.0.0.0", "--port", "8765"]
