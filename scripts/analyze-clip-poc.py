#!/usr/bin/env python3
"""
Proof of Concept: Analyze a basketball clip using Claude Vision

This script:
1. Downloads a clip from MinIO (via kubectl port-forward)
2. Extracts frames using ffmpeg
3. Sends frames to Claude Vision API
4. Returns basketball analysis (shots, rebounds by team)

Usage:
    python scripts/analyze-clip-poc.py <clip_id> [--home-color COLOR] [--away-color COLOR]

Example:
    python scripts/analyze-clip-poc.py 4763ae5a-3fc1-4bc6-be38-7b4ee51632af --home-color white --away-color dark
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("Please install anthropic: pip install anthropic")
    sys.exit(1)


def get_clip_from_minio(clip_id: str, output_path: str) -> bool:
    """Download clip from MinIO using kubectl port-forward"""

    # Use kubectl to copy the clip via the backend pod
    clip_path = f"clips/{clip_id}.mp4"

    print(f"Downloading clip {clip_id} from MinIO...")

    # Execute in backend pod to download from MinIO and output to stdout
    cmd = [
        "kubectl", "exec", "-n", "film-review",
        "deployment/basketball-film-review-backend", "--",
        "python", "-c", f'''
import sys
from minio import Minio

client = Minio(
    "minio:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False
)

try:
    response = client.get_object("basketball-clips", "{clip_path}")
    sys.stdout.buffer.write(response.read())
    response.close()
    response.release_conn()
except Exception as e:
    print(f"Error: {{e}}", file=sys.stderr)
    sys.exit(1)
'''
    ]

    with open(output_path, 'wb') as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE,
                                env={**os.environ, "KUBECONFIG": "admin.app-eng.kubeconfig"})

    if result.returncode != 0:
        print(f"Error downloading clip: {result.stderr.decode()}")
        return False

    # Verify file was downloaded
    if os.path.getsize(output_path) == 0:
        print("Error: Downloaded file is empty")
        return False

    print(f"Downloaded clip to {output_path} ({os.path.getsize(output_path)} bytes)")
    return True


def extract_frames(video_path: str, output_dir: str, fps: float = 2.0) -> list[str]:
    """Extract frames from video at specified FPS"""

    print(f"Extracting frames at {fps} fps...")

    output_pattern = os.path.join(output_dir, "frame_%04d.jpg")

    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "2",  # High quality JPEG
        output_pattern,
        "-y"  # Overwrite
    ]

    result = subprocess.run(cmd, capture_output=True)

    if result.returncode != 0:
        print(f"Error extracting frames: {result.stderr.decode()}")
        return []

    # Get list of extracted frames
    frames = sorted(Path(output_dir).glob("frame_*.jpg"))
    print(f"Extracted {len(frames)} frames")

    return [str(f) for f in frames]


def encode_image_base64(image_path: str) -> str:
    """Encode image to base64"""
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def analyze_with_claude(frames: list[str], home_color: str, away_color: str, api_key: str) -> dict:
    """Send frames to Claude Vision for analysis"""

    print(f"Analyzing {len(frames)} frames with Claude Vision...")

    client = anthropic.Anthropic(api_key=api_key)

    # Build the message content with all frames
    content = []

    # Add instruction text first
    content.append({
        "type": "text",
        "text": f"""You are analyzing a basketball game clip. The frames below are in chronological order at approximately 2 frames per second.

Team identification:
- HOME team is wearing {home_color} jerseys
- AWAY team is wearing {away_color} jerseys

Please analyze these frames and count:
1. Shot attempts by each team (any time a player shoots toward the basket)
2. Shots made (ball goes through the hoop) vs missed
3. Offensive rebounds (team retrieves their own missed shot)
4. Defensive rebounds (team retrieves opponent's missed shot)

Focus on TEAM-level statistics, not individual players. Watch carefully for:
- The ball trajectory toward the basket
- Whether shots go in or miss
- Who secures the ball after a missed shot

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

    # Add the request for structured output
    content.append({
        "type": "text",
        "text": """

Based on your analysis of all frames above, provide your response in this exact JSON format:
{
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
    "play_description": "Brief description of what happened in this clip",
    "confidence": "high/medium/low - how confident are you in this analysis",
    "notes": "Any issues or uncertainties in the analysis"
}

Return ONLY the JSON, no other text."""
    })

    # Call Claude API
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": content}
        ]
    )

    # Parse the response
    response_text = response.content[0].text

    # Calculate tokens used
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    # Estimate cost (Claude Sonnet pricing)
    cost = (input_tokens * 3 / 1_000_000) + (output_tokens * 15 / 1_000_000)

    print(f"API Usage: {input_tokens} input tokens, {output_tokens} output tokens")
    print(f"Estimated cost: ${cost:.4f}")

    try:
        # Try to parse as JSON, stripping markdown code blocks if present
        json_text = response_text.strip()
        if json_text.startswith("```"):
            # Remove markdown code block
            lines = json_text.split("\n")
            json_text = "\n".join(lines[1:-1])  # Remove first and last lines
        analysis = json.loads(json_text)
    except json.JSONDecodeError:
        # If not valid JSON, return raw response
        analysis = {"raw_response": response_text, "parse_error": True}

    return analysis


def main():
    parser = argparse.ArgumentParser(description="Analyze a basketball clip with Claude Vision")
    parser.add_argument("clip_id", help="UUID of the clip to analyze")
    parser.add_argument("--home-color", default="white", help="Home team jersey color (default: white)")
    parser.add_argument("--away-color", default="dark", help="Away team jersey color (default: dark)")
    parser.add_argument("--fps", type=float, default=2.0, help="Frames per second to extract (default: 2.0)")
    parser.add_argument("--api-key", default=os.environ.get("ANTHROPIC_API_KEY"),
                        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")

    args = parser.parse_args()

    if not args.api_key:
        print("Error: Please provide --api-key or set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)

    # Create temp directory for working files
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "clip.mp4")
        frames_dir = os.path.join(tmpdir, "frames")
        os.makedirs(frames_dir)

        # Step 1: Download clip
        if not get_clip_from_minio(args.clip_id, video_path):
            sys.exit(1)

        # Step 2: Extract frames
        frames = extract_frames(video_path, frames_dir, args.fps)
        if not frames:
            print("Error: No frames extracted")
            sys.exit(1)

        # Step 3: Analyze with Claude
        analysis = analyze_with_claude(frames, args.home_color, args.away_color, args.api_key)

        # Step 4: Output results
        print("\n" + "="*60)
        print("ANALYSIS RESULTS")
        print("="*60)
        print(json.dumps(analysis, indent=2))

        if not analysis.get("parse_error"):
            print("\n" + "-"*60)
            print("SUMMARY")
            print("-"*60)
            home = analysis.get("home_team", {})
            away = analysis.get("away_team", {})
            print(f"HOME ({args.home_color}):")
            print(f"  Shots: {home.get('shots_made', 0)}/{home.get('shots_attempted', 0)}")
            print(f"  Off Rebounds: {home.get('offensive_rebounds', 0)}")
            print(f"  Def Rebounds: {home.get('defensive_rebounds', 0)}")
            print(f"AWAY ({args.away_color}):")
            print(f"  Shots: {away.get('shots_made', 0)}/{away.get('shots_attempted', 0)}")
            print(f"  Off Rebounds: {away.get('offensive_rebounds', 0)}")
            print(f"  Def Rebounds: {away.get('defensive_rebounds', 0)}")
            print(f"\nPlay: {analysis.get('play_description', 'N/A')}")
            print(f"Confidence: {analysis.get('confidence', 'N/A')}")
            if analysis.get('notes'):
                print(f"Notes: {analysis.get('notes')}")


if __name__ == "__main__":
    main()
