"""
Claude (Anthropic) provider for video analysis.

Uses Claude's vision capabilities to analyze video frames.
"""

import os
import base64
import subprocess
import tempfile
from pathlib import Path
from typing import List

import anthropic

from .base import AnalysisProvider, AnalysisConfig, AnalysisResult, TeamStats


class ClaudeProvider(AnalysisProvider):
    """
    Anthropic Claude provider for video analysis.

    Extracts frames from video and sends them to Claude Vision API.
    """

    def __init__(self):
        self.api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = os.environ.get('CLAUDE_MODEL', 'claude-sonnet-4-20250514')

    @property
    def name(self) -> str:
        return "claude"

    @property
    def supports_native_video(self) -> bool:
        return False  # Claude requires frame extraction

    def analyze(self, video_path: str, config: AnalysisConfig) -> AnalysisResult:
        """
        Analyze video by extracting frames and sending to Claude Vision.
        """
        print(f"[Claude] Analyzing video with {config.frames_per_second} fps...")

        # Extract frames to temporary directory
        with tempfile.TemporaryDirectory() as frames_dir:
            frames = self._extract_frames(video_path, frames_dir, config.frames_per_second)

            if not frames:
                return self.create_error_result("Failed to extract frames from video")

            print(f"[Claude] Extracted {len(frames)} frames")

            # Build message content
            content = self._build_message_content(frames, config)

            # Call Claude API
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    messages=[{"role": "user", "content": content}]
                )

                response_text = response.content[0].text
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens

                # Calculate cost (Claude Sonnet pricing)
                cost = (input_tokens * 3 / 1_000_000) + (output_tokens * 15 / 1_000_000)

                print(f"[Claude] API Usage: {input_tokens} input, {output_tokens} output tokens")
                print(f"[Claude] Estimated cost: ${cost:.4f}")
                print(f"\n--- Claude Response ---\n{response_text}\n--- End Response ---\n")

                # Parse response
                data = self.parse_json_response(response_text)
                return self.create_result_from_json(
                    data, response_text, input_tokens, output_tokens, cost
                )

            except Exception as e:
                print(f"[Claude] Error during analysis: {e}")
                return self.create_error_result(str(e))

    def _extract_frames(self, video_path: str, output_dir: str, fps: float) -> List[str]:
        """Extract frames from video using ffmpeg."""
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
            print(f"[Claude] ffmpeg error: {result.stderr.decode()}")
            return []

        frames = sorted(Path(output_dir).glob("frame_*.jpg"))
        return [str(f) for f in frames]

    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64."""
        with open(image_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")

    def _build_message_content(self, frames: List[str], config: AnalysisConfig) -> List[dict]:
        """Build the message content with frames and prompt."""
        content = []

        # Add initial instruction
        intro = f"""You are an expert basketball analyst reviewing game footage frame by frame.
The frames below are in chronological order at approximately {config.frames_per_second} frames per second.

"""
        content.append({"type": "text", "text": intro + self.get_analysis_prompt(config)})

        # Add frame label
        content.append({"type": "text", "text": "\n\nHere are the frames from the clip:"})

        # Add each frame
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
                    "data": self._encode_image(frame_path)
                }
            })

        # Add final instruction
        content.append({
            "type": "text",
            "text": "\n\nNow analyze what you observed and provide your response."
        })

        return content
