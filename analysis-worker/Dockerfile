FROM python:3.11-slim

WORKDIR /app

# Install ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir anthropic minio asyncpg

# Copy worker code
COPY worker.py .

# Run the worker
CMD ["python", "worker.py"]
