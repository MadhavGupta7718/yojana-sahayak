FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    tesseract-ocr \
    tesseract-ocr-hin \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
COPY scraper/requirements.txt /app/scraper/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt \
    && pip install --no-cache-dir -r /app/scraper/requirements.txt

COPY backend /app/backend
COPY scraper /app/scraper
COPY ml /app/ml
COPY database /app/database

ENV PYTHONPATH=/app:/app/backend
WORKDIR /app

CMD ["python", "-m", "scraper.scheduler.worker"]
