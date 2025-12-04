"""
Google Gemini provider for video analysis.

Uses Gemini's native video understanding capabilities for temporal analysis.
"""

import os
import time

import google.generativeai as genai

from .base import AnalysisProvider, AnalysisConfig, AnalysisResult


class GeminiProvider(AnalysisProvider):
    """
    Google Gemini provider for video analysis.

    Uses Gemini 1.5's native video understanding to process the entire
    video file directly, enabling temporal reasoning across the clip.
    """

    def __init__(self):
        self.api_key = os.environ.get('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")

        genai.configure(api_key=self.api_key)

        # Use Gemini 2.0 Flash for video understanding (supports video natively)
        # Can override with GEMINI_MODEL env var
        model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def supports_native_video(self) -> bool:
        return True  # Gemini can process video directly!

    def analyze(self, video_path: str, config: AnalysisConfig) -> AnalysisResult:
        """
        Analyze video using Gemini's native video understanding.
        """
        print(f"[Gemini] Uploading video for analysis...")

        try:
            # Upload video file to Gemini
            video_file = genai.upload_file(path=video_path)

            # Wait for processing
            print(f"[Gemini] Processing video (this may take a moment)...")
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)

            if video_file.state.name == "FAILED":
                return self.create_error_result(f"Video processing failed: {video_file.state.name}")

            print(f"[Gemini] Video ready, sending to {self.model_name}...")

            # Build prompt
            prompt = self._build_prompt(config)

            # Generate response with video
            response = self.model.generate_content(
                [video_file, prompt],
                generation_config=genai.GenerationConfig(
                    max_output_tokens=2048,
                    temperature=0.1,  # Lower temperature for more consistent analysis
                )
            )

            response_text = response.text

            # Get token counts if available
            input_tokens = 0
            output_tokens = 0
            if hasattr(response, 'usage_metadata'):
                input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0)
                output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0)

            # Estimate cost (Gemini 1.5 Pro pricing - video is ~$0.00025/sec)
            # For simplicity, estimate based on tokens
            if 'flash' in self.model_name.lower():
                cost = (input_tokens * 0.075 / 1_000_000) + (output_tokens * 0.30 / 1_000_000)
            else:  # Pro
                cost = (input_tokens * 1.25 / 1_000_000) + (output_tokens * 5.0 / 1_000_000)

            print(f"[Gemini] Tokens: {input_tokens} input, {output_tokens} output")
            print(f"[Gemini] Estimated cost: ${cost:.4f}")
            print(f"\n--- Gemini Response ---\n{response_text}\n--- End Response ---\n")

            # Clean up uploaded file
            try:
                genai.delete_file(video_file.name)
            except Exception as e:
                print(f"[Gemini] Warning: Could not delete uploaded file: {e}")

            # Parse response
            data = self.parse_json_response(response_text)
            return self.create_result_from_json(
                data, response_text, input_tokens, output_tokens, cost
            )

        except Exception as e:
            print(f"[Gemini] Error during analysis: {e}")
            return self.create_error_result(str(e))

    def _build_prompt(self, config: AnalysisConfig) -> str:
        """Build the analysis prompt for Gemini."""
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

ANALYSIS INSTRUCTIONS:
1. Watch the ENTIRE video first to understand the full sequence
2. Identify which basket each team is shooting at based on jersey colors
3. Count EVERY shot attempt at each basket
4. After each miss, check: does the next shot go to the SAME basket or OPPOSITE?
   - Same basket = offensive rebound for the shooting team
   - Opposite basket = defensive rebound
5. Pay close attention to rapid sequences - multiple shots in a row at the same basket indicates offensive rebounds

Provide your analysis in this exact JSON format:
{{
    "analysis_reasoning": "Detailed breakdown of what you observed in the video, shot by shot",
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
}}

Watch the video carefully before responding. Provide your reasoning first, then the JSON."""
