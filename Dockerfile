FROM python:3.11-slim

WORKDIR /app

# Sistem dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kodu kopyala
COPY . .

# ChromaDB data dizini için env var
ENV CHROMADB_PERSIST_DIR=./data/chromadb

# Komut (override edilecek)
# Not: Bot henüz yok, container'ı çalışır tutmak için sleep
CMD ["python", "-c", "import time; time.sleep(3600)"]
