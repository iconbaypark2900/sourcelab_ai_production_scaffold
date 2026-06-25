FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SOURCELAB_API_RELOAD=false \
    SOURCELAB_PROJECT_ROOT=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data
COPY docs ./docs
COPY scripts ./scripts

RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -e ".[api,ui,ingest,retrieval,models]"

EXPOSE 8000

CMD ["sourcelab", "api", "--serve", "--host", "0.0.0.0", "--port", "8000", "--no-reload"]
