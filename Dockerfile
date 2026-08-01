FROM python:3.11-slim

# libgl/libglib: runtime deps for PyMuPDF (fitz) and sentence-transformers' torch wheel.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/uploads

ENV PORT=8000
EXPOSE 8000

# init_db() runs on FastAPI startup, not here — it needs DATABASE_URL,
# which is only available at container run time, not build time.
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
