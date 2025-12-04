FROM python:3.11-slim

WORKDIR /app

# Install ffmpeg (still needed for Claude provider frame extraction)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# - anthropic: Claude API
# - google-generativeai: Gemini API
# - replicate: Replicate API (for Qwen2-VL, etc.)
# - minio: Object storage client
# - asyncpg: PostgreSQL async driver
RUN pip install --no-cache-dir \
    anthropic \
    google-generativeai \
    replicate \
    minio \
    asyncpg

# Copy provider modules
COPY providers/ ./providers/

# Copy worker code
COPY worker.py .

# Run the worker
CMD ["python", "worker.py"]
