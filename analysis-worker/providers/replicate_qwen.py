"""
Replicate Qwen2-VL provider for video analysis.

Uses Qwen2-VL via Replicate API for native video understanding.
"""

import os
import base64
import tempfile

import replicate

from .base import AnalysisProvider, AnalysisConfig, AnalysisResult


class ReplicateQwenProvider(AnalysisProvider):
    """
    Replicate Qwen2-VL provider for video analysis.

    Uses Qwen2-VL-7B-Instruct model via Replicate API. This model supports
    native video understanding for clips up to 20+ minutes.
    """

    # Model version - can be overridden with REPLICATE_MODEL env var
    DEFAULT_MODEL = "lucataco/qwen2-vl-7b-instruct:bf57361c75677fc33d480d0c5f02926e621b2caa2000347cb74aeae9d2ca07ee"

    def __init__(self):
        self.api_token = os.environ.get('REPLICATE_API_TOKEN')
        if not self.api_token:
            raise ValueError("REPLICATE_API_TOKEN environment variable is required")

        # Set token for replicate library
        os.environ['REPLICATE_API_TOKEN'] = self.api_token

        self.model = os.environ.get('REPLICATE_MODEL', self.DEFAULT_MODEL)

    @property
    def name(self) -> str:
        return "replicate-qwen"

    @property
    def supports_native_video(self) -> bool:
        return True  # Qwen2-VL can process video natively

    def analyze(self, video_path: str, config: AnalysisConfig) -> AnalysisResult:
        """
        Analyze video using Qwen2-VL via Replicate.

        Note: Replicate requires video as URL or data URI. We convert local
        file to base64 data URI for upload.
        """
        print(f"[Replicate/Qwen2-VL] Preparing video for analysis...")

        try:
            # Read video file and convert to base64 data URI
            with open(video_path, 'rb') as f:
                video_bytes = f.read()

            video_size_mb = len(video_bytes) / (1024 * 1024)
            print(f"[Replicate/Qwen2-VL] Video size: {video_size_mb:.2f} MB")

            # Convert video to base64 data URI with video/mp4 MIME type
            video_b64 = base64.b64encode(video_bytes).decode('utf-8')
            video_data_uri = f"data:video/mp4;base64,{video_b64}"
            print(f"[Replicate/Qwen2-VL] Created data URI ({len(video_data_uri)} chars)")

            print(f"[Replicate/Qwen2-VL] Sending to model...")

            # Build prompt
            prompt = self._build_prompt(config)

            # Run prediction with data URI
            output = replicate.run(
                self.model,
                input={
                    "media": video_data_uri,
                    "prompt": prompt,
                    "max_new_tokens": 512,  # Longer output for detailed analysis
                }
            )

            # Output is typically a string or generator
            if hasattr(output, '__iter__') and not isinstance(output, str):
                response_text = ''.join(output)
            else:
                response_text = str(output)

            print(f"\n--- Qwen2-VL Response ---\n{response_text}\n--- End Response ---\n")

            # Replicate doesn't provide token counts, estimate cost based on model
            # Qwen2-VL-7B on Replicate is ~$0.00025/second of compute
            # Rough estimate: $0.01 per analysis
            cost = 0.01

            # Parse response
            data = self.parse_json_response(response_text)
            return self.create_result_from_json(
                data, response_text, 0, 0, cost
            )

        except Exception as e:
            print(f"[Replicate/Qwen2-VL] Error during analysis: {e}")
            return self.create_error_result(str(e))

    def _build_prompt(self, config: AnalysisConfig) -> str:
        """Build the analysis prompt for Qwen2-VL."""
        notes_section = ""
        if config.clip_notes:
            notes_section = f"""
CLIP NOTES (from the user who created this clip):
{config.clip_notes}
Use these notes as hints about what to look for in the video.
"""

        return f"""You are an expert basketball analyst. Watch this video clip carefully and analyze the basketball action.

TEAM IDENTIFICATION (CRITICAL):
- HOME team is wearing {config.home_team_color} jerseys/uniforms
- AWAY team is wearing {config.away_team_color} jerseys/uniforms
{notes_section}
IMPORTANT CONTEXT - FULL COURT GAME:
This is a full-court basketball game. Each team ONLY shoots at ONE basket:
- If you see shots at the same basket, they are from the SAME team
- If a team misses and then shoots at the SAME basket again = OFFENSIVE REBOUND
- If after a miss the ball goes to the OTHER end of the court = DEFENSIVE REBOUND
- Use the basket location to help identify which team is shooting

YOUR TASK: Watch the entire video and count basketball actions for EACH TEAM separately.

WHAT TO COUNT:

SHOT ATTEMPTS:
- Any time a player releases the ball toward the basket with shooting intent
- Includes: layups, jump shots, three-pointers, tip-ins, putbacks, hook shots
- A putback after an offensive rebound counts as a NEW shot attempt
- Count each distinct shot attempt ONCE

MADE SHOTS:
- Ball clearly goes through the hoop/net
- Watch for: ball dropping through net, swish, or ball going below rim

MISSED SHOTS:
- Shot attempt that doesn't go in
- Ball hits rim/backboard and bounces away, or airball

OFFENSIVE REBOUNDS:
- After a MISS, if the SAME team shoots again at the SAME basket = they got an offensive rebound
- Look for: tip-ins, putbacks, or second-chance shots
- Each time a team gets another shot at the same basket after a miss = 1 offensive rebound

DEFENSIVE REBOUNDS:
- After a MISS, if the ball goes to the OTHER end of the court = defensive rebound
- Or if the opposing team clearly gains possession

RESPOND WITH ONLY THIS JSON FORMAT (no other text):
{{
    "analysis_reasoning": "Detailed breakdown of what you observed",
    "home_team": {{
        "shots_attempted": 0,
        "shots_made": 0,
        "offensive_rebounds": 0,
        "defensive_rebounds": 0
    }},
    "away_team": {{
        "shots_attempted": 0,
        "shots_made": 0,
        "offensive_rebounds": 0,
        "defensive_rebounds": 0
    }},
    "play_description": "Brief summary of the play sequence",
    "confidence": "high/medium/low",
    "notes": "Any issues with video quality or uncertainty"
}}"""
