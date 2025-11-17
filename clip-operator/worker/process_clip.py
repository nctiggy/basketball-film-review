#!/usr/bin/env python3
"""
Clip Processor Worker

This script runs in a Kubernetes Job to process a single video clip.
It downloads the source video from MinIO, uses ffmpeg to extract the clip,
uploads the result back to MinIO, and updates the database status.
"""
import os
import sys
import tempfile
import subprocess
import asyncpg
from minio import Minio
from datetime import timedelta
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_timestamp(timestamp: str) -> float:
    """Convert timestamp string (mm:ss or hh:mm:ss) to seconds"""
    parts = timestamp.split(':')
    if len(parts) == 2:  # mm:ss
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:  # hh:mm:ss
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    else:
        raise ValueError(f"Invalid timestamp format: {timestamp}")


async def update_clip_status(clip_id: str, status: str, clip_path: str = None):
    """Update clip status in database"""
    database_url = os.environ['DATABASE_URL']

    conn = await asyncpg.connect(database_url)
    try:
        if clip_path:
            await conn.execute(
                "UPDATE clips SET status = $1, clip_path = $2 WHERE id = $3",
                status, clip_path, clip_id
            )
        else:
            await conn.execute(
                "UPDATE clips SET status = $1 WHERE id = $2",
                status, clip_id
            )
        logger.info(f"Updated clip {clip_id} status to {status}")
    finally:
        await conn.close()


def main():
    # Get environment variables
    clip_id = os.environ['CLIP_ID']
    video_path = os.environ['VIDEO_PATH']
    clip_path = os.environ['CLIP_PATH']
    start_time = os.environ['START_TIME']
    end_time = os.environ['END_TIME']
    minio_endpoint = os.environ['MINIO_ENDPOINT']
    minio_access_key = os.environ['MINIO_ACCESS_KEY']
    minio_secret_key = os.environ['MINIO_SECRET_KEY']
    minio_secure = os.environ.get('MINIO_SECURE', 'false').lower() == 'true'

    logger.info(f"Processing clip {clip_id}")
    logger.info(f"Video: {video_path}")
    logger.info(f"Clip path: {clip_path}")
    logger.info(f"Time range: {start_time} to {end_time}")

    # Initialize MinIO client
    minio_client = Minio(
        minio_endpoint,
        access_key=minio_access_key,
        secret_key=minio_secret_key,
        secure=minio_secure
    )

    # Create temp directory for processing
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = os.path.join(tmpdir, "input.mp4")
        output_file = os.path.join(tmpdir, "output.mp4")

        try:
            # Update status to processing
            import asyncio
            asyncio.run(update_clip_status(clip_id, 'processing'))

            # Download video from MinIO
            logger.info("Downloading video from MinIO...")
            minio_client.fget_object(
                bucket_name="basketball-videos",
                object_name=video_path,
                file_path=input_file
            )
            logger.info("Video downloaded successfully")

            # Calculate duration
            start_seconds = parse_timestamp(start_time)
            end_seconds = parse_timestamp(end_time)
            duration = end_seconds - start_seconds

            logger.info(f"Extracting clip: start={start_seconds}s, duration={duration}s")

            # Run ffmpeg with GPU acceleration
            # Using h264_nvenc for NVIDIA GPU encoding
            ffmpeg_cmd = [
                "ffmpeg",
                "-hwaccel", "cuda",  # Use CUDA for decoding
                "-ss", str(start_seconds),
                "-i", input_file,
                "-t", str(duration),
                "-c:v", "h264_nvenc",  # NVIDIA GPU encoder
                "-preset", "fast",
                "-c:a", "aac",
                "-b:a", "128k",
                "-y",  # Overwrite output
                output_file
            ]

            logger.info(f"Running ffmpeg: {' '.join(ffmpeg_cmd)}")
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                check=True
            )

            logger.info("Clip created successfully")

            # Upload clip to MinIO
            logger.info("Uploading clip to MinIO...")
            minio_client.fput_object(
                bucket_name="basketball-videos",
                object_name=clip_path,
                file_path=output_file,
                content_type="video/mp4"
            )
            logger.info("Clip uploaded successfully")

            # Update database status to completed
            asyncio.run(update_clip_status(clip_id, 'completed', clip_path))

            logger.info(f"Clip {clip_id} processed successfully!")
            sys.exit(0)

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed: {e.stderr}")
            import asyncio
            asyncio.run(update_clip_status(clip_id, 'failed'))
            sys.exit(1)

        except Exception as e:
            logger.error(f"Error processing clip: {e}", exc_info=True)
            import asyncio
            asyncio.run(update_clip_status(clip_id, 'failed'))
            sys.exit(1)


if __name__ == "__main__":
    main()
