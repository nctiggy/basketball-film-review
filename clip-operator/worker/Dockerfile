FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

# Install Python and ffmpeg with NVIDIA support
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY process_clip.py .

CMD ["python3", "process_clip.py"]
