#!/usr/bin/env python3
"""
Analysis Worker - Downloads a clip, extracts frames, sends to Claude Vision API,
and updates the database with the analysis results.
"""

import os
import sys
import json
import base64
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime

import anthropic
import asyncpg
import asyncio
from minio import Minio

# Configuration from environment
CLIP_ID = os.environ['CLIP_ID']
GAME_ID = os.environ['GAME_ID']
CLIP_PATH = os.environ['CLIP_PATH']
HOME_TEAM_COLOR = os.environ['HOME_TEAM_COLOR']
AWAY_TEAM_COLOR = os.environ['AWAY_TEAM_COLOR']
FRAMES_PER_SECOND = float(os.environ.get('FRAMES_PER_SECOND', '4.0'))
MINIO_ENDPOINT = os.environ['MINIO_ENDPOINT']
MINIO_BUCKET = os.environ.get('MINIO_BUCKET', 'basketball-clips')
MINIO_ACCESS_KEY = os.environ['MINIO_ACCESS_KEY']
MINIO_SECRET_KEY = os.environ['MINIO_SECRET_KEY']
ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']
DATABASE_URL = os.environ['DATABASE_URL']


def get_minio_client():
    """Create MinIO client"""
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )


def download_clip(minio_client: Minio, clip_path: str, output_path: str) -> bool:
    """Download clip from MinIO"""
    print(f"Downloading clip from {clip_path}...")
    try:
        minio_client.fget_object(MINIO_BUCKET, clip_path, output_path)
        size = os.path.getsize(output_path)
        print(f"Downloaded {size} bytes to {output_path}")
        return True
    except Exception as e:
        print(f"Error downloading clip: {e}")
        return False


def extract_frames(video_path: str, output_dir: str, fps: float) -> list:
    """Extract frames from video at specified FPS"""
    print(f"Extracting frames at {fps} fps...")
    output_pattern = os.path.join(output_dir, "frame_%04d.jpg")

    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "2",
        output_pattern,
        "-y"
    ]

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(f"Error extracting frames: {result.stderr.decode()}")
        return []

    frames = sorted(Path(output_dir).glob("frame_*.jpg"))
    print(f"Extracted {len(frames)} frames")
    return [str(f) for f in frames]


def encode_image_base64(image_path: str) -> str:
    """Encode image to base64"""
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def analyze_with_claude(frames: list, home_color: str, away_color: str) -> dict:
    """Send frames to Claude Vision for analysis"""
    print(f"Analyzing {len(frames)} frames with Claude Vision...")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Build the message content
    content = []

    # Add instruction text with improved prompt
    content.append({
        "type": "text",
        "text": f"""You are an expert basketball analyst reviewing game footage frame by frame. The frames below are in chronological order at approximately {FRAMES_PER_SECOND} frames per second.

TEAM IDENTIFICATION (CRITICAL - identify jersey colors first):
- HOME team is wearing {home_color} jerseys/uniforms
- AWAY team is wearing {away_color} jerseys/uniforms

YOUR TASK: Count basketball actions for EACH TEAM separately.

WHAT COUNTS AS A SHOT ATTEMPT:
- A player releasing the ball toward the basket with shooting motion
- Layups, jump shots, three-pointers, and tip-ins ALL count as shot attempts
- Watch for: arm extension toward basket, ball trajectory toward rim, shooting form
- IMPORTANT: If you see the same shot attempt across multiple frames, count it ONCE

WHAT COUNTS AS A MADE SHOT:
- Ball clearly goes through the net/hoop
- Watch for: ball dropping through net, ball below rim after being above it

WHAT COUNTS AS A MISSED SHOT:
- Shot attempt where ball hits rim/backboard and bounces away, or misses entirely
- After a miss, watch who gets the rebound

OFFENSIVE REBOUND:
- The team that SHOT and MISSED gets the ball back
- This often leads to another shot attempt (second chance)
- Watch for: players from shooting team grabbing ball after miss

DEFENSIVE REBOUND:
- The OPPOSING team (defenders) gets the ball after a missed shot
- Watch for: defenders boxing out and securing the ball

ANALYSIS APPROACH:
1. First, identify which team has the ball in each frame
2. Track ball movement toward the basket
3. Note every shooting motion you see
4. After each shot, determine: made or missed?
5. After each miss, determine: who got the rebound?
6. Count second/third chance shots as ADDITIONAL shot attempts

Here are the frames from the clip:"""
    })

    # Add each frame as an image
    for i, frame_path in enumerate(frames):
        content.append({
            "type": "text",
            "text": f"\n--- Frame {i+1}/{len(frames)} ---"
        })
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": encode_image_base64(frame_path)
            }
        })

    # Add the request for structured output with chain-of-thought
    content.append({
        "type": "text",
        "text": """

Now, analyze what you saw in these frames. Think through it step by step:

1. JERSEY COLORS: What colors did you observe for each team?
2. POSSESSION TRACKING: Which team had the ball and when did possession change?
3. SHOT-BY-SHOT BREAKDOWN: For each shot attempt you observed:
   - Which team took the shot?
   - What type of shot (layup, jumper, etc.)?
   - Did it go in or miss?
   - If missed, who got the rebound?

After your analysis, provide your final counts in this exact JSON format:
{
    "analysis_reasoning": "Your step-by-step breakdown of what you observed",
    "home_team": {
        "shots_attempted": 0,
        "shots_made": 0,
        "offensive_rebounds": 0,
        "defensive_rebounds": 0
    },
    "away_team": {
        "shots_attempted": 0,
        "shots_made": 0,
        "offensive_rebounds": 0,
        "defensive_rebounds": 0
    },
    "play_description": "Brief summary of what happened in this clip",
    "confidence": "high/medium/low",
    "notes": "Any issues with video quality, camera angle, or uncertainty"
}

Provide your reasoning first, then the JSON."""
    })

    # Call Claude API
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[
            {"role": "user", "content": content}
        ]
    )

    response_text = response.content[0].text

    # Calculate tokens used
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost = (input_tokens * 3 / 1_000_000) + (output_tokens * 15 / 1_000_000)

    print(f"API Usage: {input_tokens} input tokens, {output_tokens} output tokens")
    print(f"Estimated cost: ${cost:.4f}")

    # Parse response - extract JSON from the response which may include reasoning text
    try:
        # Print the full response for debugging
        print(f"\n--- Claude Response ---\n{response_text}\n--- End Response ---\n")

        # Find JSON in the response (it may be preceded by reasoning text)
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON found in response")

        json_text = response_text[json_start:json_end]

        # Clean up any markdown code blocks
        if "```" in json_text:
            # Extract content between code blocks
            lines = json_text.split("\n")
            cleaned_lines = []
            in_code_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_code_block = not in_code_block
                    continue
                cleaned_lines.append(line)
            json_text = "\n".join(cleaned_lines)
            # Re-find JSON boundaries
            json_start = json_text.find('{')
            json_end = json_text.rfind('}') + 1
            json_text = json_text[json_start:json_end]

        analysis = json.loads(json_text)

        # Store reasoning in notes if present
        if 'analysis_reasoning' in analysis:
            reasoning = analysis.pop('analysis_reasoning')
            existing_notes = analysis.get('notes', '') or ''
            analysis['notes'] = f"{reasoning}\n\n{existing_notes}".strip() if existing_notes else reasoning

    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error parsing JSON response: {e}")
        print(f"Raw response: {response_text}")
        analysis = {
            "parse_error": True,
            "raw_response": response_text,
            "home_team": {"shots_attempted": 0, "shots_made": 0, "offensive_rebounds": 0, "defensive_rebounds": 0},
            "away_team": {"shots_attempted": 0, "shots_made": 0, "offensive_rebounds": 0, "defensive_rebounds": 0},
            "play_description": "Error parsing response",
            "confidence": "low",
            "notes": f"JSON parse error: {e}"
        }

    return analysis


async def update_database(analysis: dict):
    """Update the database with analysis results"""
    print("Updating database with analysis results...")

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        home = analysis.get('home_team', {})
        away = analysis.get('away_team', {})

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
            analysis.get('play_description'),
            analysis.get('confidence'),
            analysis.get('notes'),
            CLIP_ID
        )

        print("Database updated successfully")

    finally:
        await conn.close()


async def update_status(status: str, error_message: str = None):
    """Update the analysis status in the database"""
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
    print(f"Starting analysis for clip {CLIP_ID}")
    print(f"  Clip path: {CLIP_PATH}")
    print(f"  Home team color: {HOME_TEAM_COLOR}")
    print(f"  Away team color: {AWAY_TEAM_COLOR}")
    print(f"  FPS: {FRAMES_PER_SECOND}")

    # Update status to processing
    asyncio.run(update_status('processing'))

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "clip.mp4")
            frames_dir = os.path.join(tmpdir, "frames")
            os.makedirs(frames_dir)

            # Download clip from MinIO
            minio_client = get_minio_client()
            if not download_clip(minio_client, CLIP_PATH, video_path):
                raise Exception("Failed to download clip from MinIO")

            # Extract frames
            frames = extract_frames(video_path, frames_dir, FRAMES_PER_SECOND)
            if not frames:
                raise Exception("Failed to extract frames from video")

            # Analyze with Claude
            analysis = analyze_with_claude(frames, HOME_TEAM_COLOR, AWAY_TEAM_COLOR)

            # Update database
            asyncio.run(update_database(analysis))

            # Print summary
            print("\n" + "="*60)
            print("ANALYSIS COMPLETE")
            print("="*60)
            home = analysis.get('home_team', {})
            away = analysis.get('away_team', {})
            print(f"HOME ({HOME_TEAM_COLOR}):")
            print(f"  Shots: {home.get('shots_made', 0)}/{home.get('shots_attempted', 0)}")
            print(f"  Off Rebounds: {home.get('offensive_rebounds', 0)}")
            print(f"  Def Rebounds: {home.get('defensive_rebounds', 0)}")
            print(f"AWAY ({AWAY_TEAM_COLOR}):")
            print(f"  Shots: {away.get('shots_made', 0)}/{away.get('shots_attempted', 0)}")
            print(f"  Off Rebounds: {away.get('offensive_rebounds', 0)}")
            print(f"  Def Rebounds: {away.get('defensive_rebounds', 0)}")
            print(f"\nPlay: {analysis.get('play_description', 'N/A')}")
            print(f"Confidence: {analysis.get('confidence', 'N/A')}")

    except Exception as e:
        print(f"Error during analysis: {e}")
        asyncio.run(update_status('failed', str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
