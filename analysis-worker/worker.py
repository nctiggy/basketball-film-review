#!/usr/bin/env python3
"""
Analysis Worker - Downloads a clip, analyzes it using a configurable AI provider,
and updates the database with the analysis results.

Supports multiple AI providers:
- claude: Anthropic Claude (frame-by-frame analysis)
- gemini: Google Gemini (native video understanding)
"""

import os
import sys
import tempfile
import asyncio

import asyncpg
from minio import Minio

from providers import get_provider, AnalysisConfig

# Configuration from environment
CLIP_ID = os.environ['CLIP_ID']
GAME_ID = os.environ['GAME_ID']
CLIP_PATH = os.environ['CLIP_PATH']
HOME_TEAM_COLOR = os.environ['HOME_TEAM_COLOR']
AWAY_TEAM_COLOR = os.environ['AWAY_TEAM_COLOR']
FRAMES_PER_SECOND = float(os.environ.get('FRAMES_PER_SECOND', '4.0'))
CLIP_NOTES = os.environ.get('CLIP_NOTES', '')

# Provider selection - defaults to gemini for native video support
ANALYSIS_PROVIDER = os.environ.get('ANALYSIS_PROVIDER', 'gemini')

# MinIO configuration
MINIO_ENDPOINT = os.environ['MINIO_ENDPOINT']
MINIO_BUCKET = os.environ.get('MINIO_BUCKET', 'basketball-clips')
MINIO_ACCESS_KEY = os.environ['MINIO_ACCESS_KEY']
MINIO_SECRET_KEY = os.environ['MINIO_SECRET_KEY']

# Database
DATABASE_URL = os.environ['DATABASE_URL']


def get_minio_client():
    """Create MinIO client."""
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )


def download_clip(minio_client: Minio, clip_path: str, output_path: str) -> bool:
    """Download clip from MinIO."""
    print(f"Downloading clip from {clip_path}...")
    try:
        minio_client.fget_object(MINIO_BUCKET, clip_path, output_path)
        size = os.path.getsize(output_path)
        print(f"Downloaded {size} bytes to {output_path}")
        return True
    except Exception as e:
        print(f"Error downloading clip: {e}")
        return False


async def update_database(analysis_result):
    """Update the database with analysis results."""
    print("Updating database with analysis results...")

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        result = analysis_result.to_dict()
        home = result.get('home_team', {})
        away = result.get('away_team', {})

        await conn.execute("""
            UPDATE clip_analyses SET
                home_shots_attempted = $1,
                home_shots_made = $2,
                home_offensive_rebounds = $3,
                home_defensive_rebounds = $4,
                away_shots_attempted = $5,
                away_shots_made = $6,
                away_offensive_rebounds = $7,
                away_defensive_rebounds = $8,
                play_description = $9,
                confidence = $10,
                notes = $11,
                status = 'completed',
                completed_at = NOW()
            WHERE clip_id = $12
        """,
            home.get('shots_attempted', 0),
            home.get('shots_made', 0),
            home.get('offensive_rebounds', 0),
            home.get('defensive_rebounds', 0),
            away.get('shots_attempted', 0),
            away.get('shots_made', 0),
            away.get('offensive_rebounds', 0),
            away.get('defensive_rebounds', 0),
            result.get('play_description'),
            result.get('confidence'),
            result.get('notes'),
            CLIP_ID
        )

        print("Database updated successfully")

    finally:
        await conn.close()


async def update_status(status: str, error_message: str = None):
    """Update the analysis status in the database."""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        if error_message:
            await conn.execute(
                "UPDATE clip_analyses SET status = $1, error_message = $2 WHERE clip_id = $3",
                status, error_message, CLIP_ID
            )
        else:
            await conn.execute(
                "UPDATE clip_analyses SET status = $1 WHERE clip_id = $2",
                status, CLIP_ID
            )
    finally:
        await conn.close()


def main():
    print(f"{'='*60}")
    print(f"ANALYSIS WORKER")
    print(f"{'='*60}")
    print(f"  Clip ID: {CLIP_ID}")
    print(f"  Clip path: {CLIP_PATH}")
    print(f"  Home team color: {HOME_TEAM_COLOR}")
    print(f"  Away team color: {AWAY_TEAM_COLOR}")
    print(f"  Provider: {ANALYSIS_PROVIDER}")
    print(f"  FPS (for frame-based providers): {FRAMES_PER_SECOND}")
    if CLIP_NOTES:
        print(f"  Notes: {CLIP_NOTES[:100]}...")
    print(f"{'='*60}")

    # Update status to processing
    asyncio.run(update_status('processing'))

    try:
        # Initialize provider
        print(f"\nInitializing {ANALYSIS_PROVIDER} provider...")
        provider = get_provider(ANALYSIS_PROVIDER)
        print(f"Provider: {provider.name}")
        print(f"Native video support: {provider.supports_native_video}")

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "clip.mp4")

            # Download clip from MinIO
            minio_client = get_minio_client()
            if not download_clip(minio_client, CLIP_PATH, video_path):
                raise Exception("Failed to download clip from MinIO")

            # Create analysis config
            config = AnalysisConfig(
                home_team_color=HOME_TEAM_COLOR,
                away_team_color=AWAY_TEAM_COLOR,
                frames_per_second=FRAMES_PER_SECOND,
                clip_notes=CLIP_NOTES if CLIP_NOTES else None,
            )

            # Run analysis
            print(f"\nStarting analysis with {provider.name}...")
            result = provider.analyze(video_path, config)

            # Update database
            asyncio.run(update_database(result))

            # Print summary
            print("\n" + "="*60)
            print("ANALYSIS COMPLETE")
            print("="*60)
            print(f"Provider: {result.provider}")
            home = result.home_team
            away = result.away_team
            print(f"HOME ({HOME_TEAM_COLOR}):")
            print(f"  Shots: {home.shots_made}/{home.shots_attempted}")
            print(f"  Off Rebounds: {home.offensive_rebounds}")
            print(f"  Def Rebounds: {home.defensive_rebounds}")
            print(f"AWAY ({AWAY_TEAM_COLOR}):")
            print(f"  Shots: {away.shots_made}/{away.shots_attempted}")
            print(f"  Off Rebounds: {away.offensive_rebounds}")
            print(f"  Def Rebounds: {away.defensive_rebounds}")
            print(f"\nPlay: {result.play_description or 'N/A'}")
            print(f"Confidence: {result.confidence or 'N/A'}")
            if result.cost_estimate > 0:
                print(f"Cost: ${result.cost_estimate:.4f}")

    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        asyncio.run(update_status('failed', str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
