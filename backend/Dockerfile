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
# CPU torch first (smaller than default CUDA wheel), then ML deps from requirements
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY scraper /app/scraper
COPY ml /app/ml
COPY database /app/database

ENV PYTHONPATH=/app:/app/backend
WORKDIR /app/backend

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
