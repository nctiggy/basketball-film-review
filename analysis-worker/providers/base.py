"""
Base classes and interfaces for analysis providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class AnalysisConfig:
    """Configuration for video analysis."""
    home_team_color: str
    away_team_color: str
    frames_per_second: float = 4.0
    clip_notes: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TeamStats:
    """Statistics for a single team."""
    shots_attempted: int = 0
    shots_made: int = 0
    offensive_rebounds: int = 0
    defensive_rebounds: int = 0


@dataclass
class AnalysisResult:
    """Result from video analysis."""
    home_team: TeamStats
    away_team: TeamStats
    play_description: Optional[str] = None
    confidence: str = "medium"
    notes: Optional[str] = None
    raw_response: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_estimate: float = 0.0
    provider: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'home_team': {
                'shots_attempted': self.home_team.shots_attempted,
                'shots_made': self.home_team.shots_made,
                'offensive_rebounds': self.home_team.offensive_rebounds,
                'defensive_rebounds': self.home_team.defensive_rebounds,
            },
            'away_team': {
                'shots_attempted': self.away_team.shots_attempted,
                'shots_made': self.away_team.shots_made,
                'offensive_rebounds': self.away_team.offensive_rebounds,
                'defensive_rebounds': self.away_team.defensive_rebounds,
            },
            'play_description': self.play_description,
            'confidence': self.confidence,
            'notes': self.notes,
        }


class AnalysisProvider(ABC):
    """
    Abstract base class for video analysis providers.

    Each provider implements the analyze method to process video
    using their specific AI model/API.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        pass

    @property
    @abstractmethod
    def supports_native_video(self) -> bool:
        """Return True if provider can process video directly (not just frames)."""
        pass

    @abstractmethod
    def analyze(self, video_path: str, config: AnalysisConfig) -> AnalysisResult:
        """
        Analyze a video clip and return statistics.

        Args:
            video_path: Path to the video file
            config: Analysis configuration including team colors

        Returns:
            AnalysisResult with team statistics and play description
        """
        pass

    def get_analysis_prompt(self, config: AnalysisConfig) -> str:
        """
        Generate the analysis prompt. Can be overridden by providers.

        Args:
            config: Analysis configuration

        Returns:
            Prompt string for the model
        """
        notes_section = ""
        if config.clip_notes:
            notes_section = f"""
CLIP NOTES (from the user who created this clip):
{config.clip_notes}
Use these notes as hints about what to look for in the video.
"""

        return f"""You are an expert basketball analyst reviewing game footage.

TEAM IDENTIFICATION (CRITICAL - identify jersey colors first):
- HOME team is wearing {config.home_team_color} jerseys/uniforms
- AWAY team is wearing {config.away_team_color} jerseys/uniforms
{notes_section}
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
1. First, identify which team has the ball
2. Track ball movement toward the basket
3. Note every shooting motion you see
4. After each shot, determine: made or missed?
5. After each miss, determine: who got the rebound?
6. Count second/third chance shots as ADDITIONAL shot attempts

Analyze what you see and provide your response in this exact JSON format:
{{
    "analysis_reasoning": "Your step-by-step breakdown of what you observed",
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
    "play_description": "Brief summary of what happened in this clip",
    "confidence": "high/medium/low",
    "notes": "Any issues with video quality, camera angle, or uncertainty"
}}

Provide your reasoning first, then the JSON."""

    def parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON from model response, handling reasoning text before JSON.

        Args:
            response_text: Raw response from the model

        Returns:
            Parsed JSON as dictionary
        """
        import json

        # Find JSON in the response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON found in response")

        json_text = response_text[json_start:json_end]

        # Clean up any markdown code blocks
        if "```" in json_text:
            lines = json_text.split("\n")
            cleaned_lines = []
            in_code_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_code_block = not in_code_block
                    continue
                cleaned_lines.append(line)
            json_text = "\n".join(cleaned_lines)
            json_start = json_text.find('{')
            json_end = json_text.rfind('}') + 1
            json_text = json_text[json_start:json_end]

        return json.loads(json_text)

    def create_result_from_json(
        self,
        data: Dict[str, Any],
        raw_response: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0
    ) -> AnalysisResult:
        """
        Create AnalysisResult from parsed JSON data.

        Args:
            data: Parsed JSON response
            raw_response: Original response text
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
            cost: Estimated cost

        Returns:
            AnalysisResult instance
        """
        home = data.get('home_team', {})
        away = data.get('away_team', {})

        # Build notes from reasoning if present
        notes = data.get('notes', '')
        if 'analysis_reasoning' in data:
            reasoning = data['analysis_reasoning']
            notes = f"{reasoning}\n\n{notes}".strip() if notes else reasoning

        return AnalysisResult(
            home_team=TeamStats(
                shots_attempted=home.get('shots_attempted', 0),
                shots_made=home.get('shots_made', 0),
                offensive_rebounds=home.get('offensive_rebounds', 0),
                defensive_rebounds=home.get('defensive_rebounds', 0),
            ),
            away_team=TeamStats(
                shots_attempted=away.get('shots_attempted', 0),
                shots_made=away.get('shots_made', 0),
                offensive_rebounds=away.get('offensive_rebounds', 0),
                defensive_rebounds=away.get('defensive_rebounds', 0),
            ),
            play_description=data.get('play_description'),
            confidence=data.get('confidence', 'medium'),
            notes=notes,
            raw_response=raw_response,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_estimate=cost,
            provider=self.name,
        )

    def create_error_result(self, error: str, raw_response: str = "") -> AnalysisResult:
        """Create a result indicating an error occurred."""
        return AnalysisResult(
            home_team=TeamStats(),
            away_team=TeamStats(),
            play_description="Error during analysis",
            confidence="low",
            notes=f"Analysis error: {error}",
            raw_response=raw_response,
            provider=self.name,
        )
