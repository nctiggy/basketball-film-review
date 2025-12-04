"""
Model Provider Interface for Video Analysis

This module provides a pluggable architecture for different AI model providers
to analyze basketball video clips.
"""

from .base import AnalysisProvider, AnalysisConfig, AnalysisResult
from .claude import ClaudeProvider
from .gemini import GeminiProvider
from .replicate_qwen import ReplicateQwenProvider

# Registry of available providers
PROVIDERS = {
    'claude': ClaudeProvider,
    'gemini': GeminiProvider,
    'replicate-qwen': ReplicateQwenProvider,
    'qwen': ReplicateQwenProvider,  # Alias for convenience
}


def get_provider(provider_name: str) -> AnalysisProvider:
    """
    Factory function to get a provider instance by name.

    Args:
        provider_name: Name of the provider ('claude', 'gemini', etc.)

    Returns:
        An instance of the requested provider

    Raises:
        ValueError: If provider_name is not recognized
    """
    provider_name = provider_name.lower()
    if provider_name not in PROVIDERS:
        available = ', '.join(PROVIDERS.keys())
        raise ValueError(f"Unknown provider '{provider_name}'. Available: {available}")

    return PROVIDERS[provider_name]()


__all__ = [
    'AnalysisProvider',
    'AnalysisConfig',
    'AnalysisResult',
    'ClaudeProvider',
    'GeminiProvider',
    'ReplicateQwenProvider',
    'get_provider',
    'PROVIDERS',
]
