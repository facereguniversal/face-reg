FROM python:3.11-slim

WORKDIR /app

# System dependencies for OpenCV runtime (libGL, libglib)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY ingestion/ ./ingestion/
COPY db/ ./db/
COPY model_server/ ./model_server/

EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
